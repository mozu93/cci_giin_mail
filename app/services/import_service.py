from datetime import datetime
from pathlib import Path
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.database.models import Position, Committee, MemberHistory
from app.services.member_service import (
    create_member, update_member, set_email_addresses,
    record_member_history, get_members
)
from app.utils import to_hankaku_kana


_CSV_ENCODINGS = ["utf-8-sig", "cp932", "utf-8", "euc-jp"]


def _read_csv_auto(filepath: str) -> list[list]:
    import csv
    raw = Path(filepath).read_bytes()
    for enc in _CSV_ENCODINGS:
        try:
            text = raw.decode(enc)
            reader = csv.reader(text.splitlines())
            return [list(r) for r in reader]
        except (UnicodeDecodeError, LookupError):
            continue
    # 最終フォールバック: 読めない文字を置換
    text = raw.decode("cp932", errors="replace")
    reader = csv.reader(text.splitlines())
    return [list(r) for r in reader]


def load_member_file(filepath: str) -> tuple[list[str], list[list]]:
    ext = Path(filepath).suffix.lower()
    if ext in (".xlsx", ".xls"):
        import openpyxl
        wb = openpyxl.load_workbook(filepath, read_only=True, data_only=True)
        ws = wb.active
        rows = list(ws.iter_rows(values_only=True))
        wb.close()
    elif ext == ".csv":
        import csv
        rows = _read_csv_auto(filepath)
    else:
        raise ValueError(f"非対応のファイル形式: {ext}")
    if not rows:
        return [], []
    headers = [str(h) if h is not None else "" for h in rows[0]]
    data_rows = [list(r) for r in rows[1:] if any(c for c in r)]
    return headers, data_rows


def import_members(session: Session, rows: list[list],
                   column_map: dict, changed_by: str) -> dict:
    # このインポートで作成・更新される MemberHistory を一括識別するためのバッチID
    batch_id = f"IMP_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{changed_by}"
    max_hist_id = session.query(func.max(MemberHistory.id)).scalar() or 0

    existing = {m.member_number: m for m in get_members(session, active_only=False)}
    position_map = {p.name: p.id for p in session.query(Position).all()}
    committee_map = {c.name: c.id for c in session.query(Committee).all()}
    created = updated = 0
    errors: list[str] = []

    def _cell(row, key):
        idx = column_map.get(key)
        if idx is None or idx >= len(row):
            return ""
        val = row[idx]
        return str(val).strip() if val is not None else ""

    for i, row in enumerate(rows, start=2):
        member_number = _cell(row, "member_number")
        if not member_number:
            errors.append(f"行{i}: 会員番号が空です")
            continue
        organization_name = _cell(row, "organization_name")
        name = _cell(row, "name")
        if not organization_name or not name:
            errors.append(f"行{i} ({member_number}): 事業所名または氏名が空です")
            continue

        kwargs = {
            "organization_kana": to_hankaku_kana(_cell(row, "organization_kana")),
            "title":             _cell(row, "title"),
            "name_kana":         to_hankaku_kana(_cell(row, "name_kana")),
        }
        if "position_name" in column_map:
            position_name = _cell(row, "position_name")
            if position_name:
                if position_name not in position_map:
                    new_pos = Position(name=position_name, sort_order=0)
                    session.add(new_pos)
                    session.flush()
                    position_map[position_name] = new_pos.id
                kwargs["position_id"] = position_map[position_name]
            else:
                kwargs["position_id"] = None

        if "committee_name" in column_map:
            committee_name = _cell(row, "committee_name")
            if committee_name:
                if committee_name not in committee_map:
                    new_committee = Committee(name=committee_name, sort_order=0)
                    session.add(new_committee)
                    session.flush()
                    committee_map[committee_name] = new_committee.id
                kwargs["committee_id"] = committee_map[committee_name]
            else:
                kwargs["committee_id"] = None

        addresses = []
        for n in range(1, 6):
            addr = _cell(row, f"email_{n}_address")
            if addr:
                addresses.append({
                    "address":    addr,
                    "label":      _cell(row, f"email_{n}_label"),
                    "sort_order": n,
                })

        savepoint = session.begin_nested()
        try:
            if member_number in existing:
                update_member(session, existing[member_number].id,
                              changed_by=changed_by,
                              change_reason="Excelインポートによる更新",
                              organization_name=organization_name,
                              name=name, commit=False, **kwargs)
                if addresses:
                    set_email_addresses(session,
                                        existing[member_number].id, addresses)
                updated += 1
            else:
                m = create_member(session, member_number,
                                  organization_name, name,
                                  commit=False, **kwargs)
                existing[member_number] = m  # 同一ファイル内の重複を更新扱いにする
                if addresses:
                    set_email_addresses(session, m.id, addresses)
                # メールアドレス設定後にスナップショットを記録
                record_member_history(session, m.id,
                                      changed_by=changed_by,
                                      change_reason="新規登録",
                                      commit=False)
                created += 1
            savepoint.commit()
        except IntegrityError:
            savepoint.rollback()
            errors.append(f"行{i} ({member_number}): 会員番号が重複しています")
        except Exception as e:
            savepoint.rollback()
            errors.append(f"行{i} ({member_number}): {e}")

    # このインポートで追加された MemberHistory 全件にバッチIDを付与
    (session.query(MemberHistory)
     .filter(MemberHistory.id > max_hist_id)
     .update({"import_batch_id": batch_id}))
    session.commit()

    return {"created": created, "updated": updated, "errors": errors,
            "batch_id": batch_id}
