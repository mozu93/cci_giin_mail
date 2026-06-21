from pathlib import Path
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.database.models import Position
from app.services.member_service import (
    create_member, update_member, set_email_addresses, get_members
)


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
    existing = {m.member_number: m for m in get_members(session, active_only=False)}
    position_map = {p.name: p.id for p in session.query(Position).all()}
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
            "organization_kana": _cell(row, "organization_kana"),
            "title":             _cell(row, "title"),
            "name_kana":         _cell(row, "name_kana"),
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

        addresses = []
        for n in range(1, 6):
            addr = _cell(row, f"email_{n}_address")
            if addr:
                addresses.append({
                    "address":    addr,
                    "label":      _cell(row, f"email_{n}_label"),
                    "sort_order": n,
                })

        try:
            if member_number in existing:
                update_member(session, existing[member_number].id,
                              changed_by=changed_by,
                              change_reason="Excelインポートによる更新",
                              organization_name=organization_name,
                              name=name, **kwargs)
                if addresses:
                    set_email_addresses(session,
                                        existing[member_number].id, addresses)
                    session.commit()
                updated += 1
            else:
                m = create_member(session, member_number,
                                  organization_name, name, **kwargs)
                existing[member_number] = m  # 同一ファイル内の重複を更新扱いにする
                if addresses:
                    set_email_addresses(session, m.id, addresses)
                    session.commit()
                created += 1
        except IntegrityError:
            errors.append(f"行{i} ({member_number}): 会員番号が重複しています")
        except Exception as e:
            errors.append(f"行{i} ({member_number}): {e}")

    return {"created": created, "updated": updated, "errors": errors}
