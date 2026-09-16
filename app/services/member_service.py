import json
from datetime import datetime
from sqlalchemy import func
from sqlalchemy.orm import Session, contains_eager, selectinload
from sqlalchemy.exc import IntegrityError
from app.database.models import Member, EmailAddress, MemberHistory, Position
from app.utils import to_katakana


COMMITTEE_ROLE_LIMITS = {"委員長": 1, "副委員長": 2}


def validate_committee_role(session: Session, committee_id: int | None,
                            committee_role: str | None,
                            exclude_member_id: int | None = None) -> None:
    """委員会内役職の人数上限（委員長1名・副委員長2名）を超えないか確認する。"""
    limit = COMMITTEE_ROLE_LIMITS.get(committee_role or "")
    if not committee_id or not limit:
        return
    q = session.query(Member).filter(
        Member.committee_id == committee_id,
        Member.committee_role == committee_role,
        Member.is_active == True,
    )
    if exclude_member_id is not None:
        q = q.filter(Member.id != exclude_member_id)
    if q.count() >= limit:
        raise ValueError(
            f"この委員会の「{committee_role}」はすでに{limit}名登録されています。")


_COMMITTEE_ROLE_TIER = {"担当副会頭": 0, "委員長": 1, "副委員長": 2}


def committee_role_display(member: Member) -> str:
    """委員会役職の表示名を返す。委員会に所属していて役職未設定の場合は「委員」とする。"""
    if member.committee_role:
        return member.committee_role
    return "委員" if member.committee_id else ""


def sort_members_by_committee_role(members: list[Member]) -> list[Member]:
    """担当副会頭→委員長→副委員長→委員の順に並べ、各グループ内は
    会議所役職順（会頭→副会頭→常議員→監事→議員）、同役職内は
    事業所名フリガナ順とする。"""
    def key(m: Member):
        tier = _COMMITTEE_ROLE_TIER.get(m.committee_role or "", 3)
        pos_order = m.position.sort_order if m.position else 10**9
        disp_order = m.display_order if m.display_order is not None else 10**9
        return (tier, pos_order, disp_order, m.organization_kana or "")
    return sorted(members, key=key)


def member_to_snapshot(member: Member) -> str:
    data = {
        "member_number":     member.member_number,
        "position_name":     member.position.name if member.position else "",
        "committee_name":    member.committee.name if member.committee else "",
        "committee_role":    member.committee_role or "",
        "organization_name": member.organization_name,
        "organization_kana": member.organization_kana,
        "title":             member.title,
        "name":              member.name,
        "name_kana":         member.name_kana,
        "notes":             member.notes,
        "is_active":         member.is_active,
        "email_addresses":   [
            {"address": e.address, "label": e.label, "sort_order": e.sort_order}
            for e in member.email_addresses
        ],
    }
    return json.dumps(data, ensure_ascii=False)


def create_member(session: Session, member_number: str,
                  organization_name: str, name: str,
                  commit: bool = True, **kwargs) -> Member:
    """会員を作成する。履歴は呼び出し元でメール設定後に record_member_history() で記録すること。

    commit=Falseの場合はflushのみ行い、コミットとエラー時のロールバックは
    呼び出し元（複数件をまとめて1トランザクションで扱う場合など）に委ねる。
    """
    member = Member(
        member_number=member_number,
        organization_name=organization_name,
        name=name,
        **kwargs
    )
    session.add(member)
    try:
        if commit:
            session.commit()
        else:
            session.flush()
    except IntegrityError:
        if commit:
            session.rollback()
        raise
    return member


def record_member_history(session: Session, member_id: int,
                          changed_by: str, change_reason: str,
                          commit: bool = True) -> None:
    """現在のメンバー状態（メールアドレス含む）をスナップショットとして履歴に記録する。
    一括変更モード中の記録は「最近の更新」一覧から除外される。"""
    member = session.get(Member, member_id)
    if member is None:
        return
    from app.utils.app_config import is_bulk_edit_mode
    session.add(MemberHistory(
        member_id=member_id,
        changed_by=changed_by or "システム",
        change_reason=change_reason,
        snapshot=member_to_snapshot(member),
        exclude_from_recent=is_bulk_edit_mode(),
    ))
    if commit:
        session.commit()
    else:
        session.flush()


def get_member(session: Session, member_id: int) -> Member | None:
    return session.get(Member, member_id)


def get_members(session: Session, position_id: int | None = None,
                committee_id: int | None = None,
                keyword: str | None = None,
                active_only: bool = True) -> list[Member]:
    q = (session.query(Member)
         .outerjoin(Member.position)
         .options(contains_eager(Member.position),
                  selectinload(Member.committee),
                  selectinload(Member.email_addresses)))
    if active_only:
        q = q.filter(Member.is_active == True)
    if position_id is not None:
        q = q.filter(Member.position_id == position_id)
    if committee_id is not None:
        q = q.filter(Member.committee_id == committee_id)
    members = q.order_by(
        Position.sort_order.asc().nullslast(),
        Member.display_order.asc().nullslast(),
        Member.organization_kana.asc(),
    ).all()
    if not keyword:
        return members

    # フリガナは入力元によって半角/全角・ひらがな/カタカナが混在し得るため、
    # DB固有の正規化関数には頼らず比較前に統一する。
    normalized_keyword = to_katakana(keyword).casefold()
    return [
        member for member in members
        if any(
            normalized_keyword in to_katakana(value or "").casefold()
            for value in (
                member.organization_name,
                member.name,
                member.member_number,
                member.organization_kana,
                member.name_kana,
            )
        )
    ]


def set_email_addresses(session: Session, member_id: int,
                        addresses: list[dict]) -> None:
    if len(addresses) > 5:
        raise ValueError("メールアドレスは最大5件まで登録できます")
    session.query(EmailAddress).filter_by(member_id=member_id).delete()
    for addr in addresses:
        session.add(EmailAddress(
            member_id=member_id,
            address=addr["address"],
            label=addr.get("label", ""),
            sort_order=addr.get("sort_order", 1),
        ))
    # メールアドレス変更でも最終更新日を更新する
    member = session.get(Member, member_id)
    if member:
        member.updated_at = datetime.now()
    session.flush()


def update_member(session: Session, member_id: int,
                  changed_by: str, change_reason: str,
                  commit: bool = True, **kwargs) -> Member:
    member = session.get(Member, member_id)
    if member is None:
        raise ValueError(f"会員ID {member_id} が見つかりません")
    # 変更前のスナップショット（メールアドレス含む）を記録
    from app.utils.app_config import is_bulk_edit_mode
    session.add(MemberHistory(
        member_id=member_id,
        changed_by=changed_by,
        change_reason=change_reason,
        snapshot=member_to_snapshot(member),
        exclude_from_recent=is_bulk_edit_mode(),
    ))
    for key, value in kwargs.items():
        setattr(member, key, value)
    member.updated_at = datetime.now()
    if commit:
        session.commit()
    else:
        session.flush()
    return member


def delete_member(session: Session, member_id: int,
                  changed_by: str = "") -> None:
    """退任処理: is_active=Falseに変更し、履歴を保持する"""
    from app.utils.app_config import is_bulk_edit_mode
    member = session.get(Member, member_id)
    if member:
        session.add(MemberHistory(
            member_id=member_id,
            changed_by=changed_by or "システム",
            change_reason="議員退任",
            snapshot=member_to_snapshot(member),
            exclude_from_recent=is_bulk_edit_mode(),
        ))
        member.is_active = False
        member.updated_at = datetime.now()
        session.commit()


def get_member_history(session: Session, member_id: int) -> list[MemberHistory]:
    return (session.query(MemberHistory)
            .filter_by(member_id=member_id)
            .order_by(MemberHistory.changed_at.desc())
            .all())


_HISTORY_FIELD_LABELS = {
    "member_number":     "会員番号",
    "position_name":     "会議所役職",
    "committee_name":    "委員会",
    "committee_role":    "委員会役職",
    "organization_name": "事業所名",
    "organization_kana": "事業所名フリガナ",
    "title":             "役職名",
    "name":              "氏名",
    "name_kana":         "氏名フリガナ",
    "notes":             "備考",
    "is_active":         "議員状態",
}


def format_history_value(key: str, value) -> str:
    if key == "is_active":
        return "在任中" if value else "議員退任"
    if value is None or value == "":
        return "（なし）"
    return str(value)


def diff_snapshots(before: dict, after: dict) -> list[dict]:
    """2つのスナップショット（member_to_snapshotのJSONをparseしたdict）を比較し、
    値が変わった項目だけを [{"field": 表示名, "old": 変更前, "new": 変更後}] で返す。"""
    diffs = []
    for key, label in _HISTORY_FIELD_LABELS.items():
        old_val = format_history_value(key, before.get(key))
        new_val = format_history_value(key, after.get(key))
        if old_val != new_val:
            diffs.append({"field": label, "old": old_val, "new": new_val})

    emails_before = before.get("email_addresses", [])
    emails_after = after.get("email_addresses", [])
    for i in range(max(len(emails_before), len(emails_after))):
        eb = emails_before[i] if i < len(emails_before) else {}
        ea = emails_after[i] if i < len(emails_after) else {}

        def _mail(e):
            addr = e.get("address", "")
            label = e.get("label", "")
            return f"{addr}（{label}）" if addr else "（なし）"
        old_val, new_val = _mail(eb), _mail(ea)
        if old_val != new_val:
            diffs.append({"field": f"メール{i + 1}", "old": old_val, "new": new_val})
    return diffs


def get_recent_changes(session: Session, limit: int = 30) -> list[dict]:
    """全会員の変更履歴を横断し、直近の変更内容を新しい順で返す。
    1件＝1回の保存操作（変更のなかった保存は含まない）で、各件に
    変更された項目ごとの変更前後の値のリストを含む。"""
    all_history = (
        session.query(MemberHistory)
        .order_by(MemberHistory.changed_at.desc())
        .all()
    )
    by_member: dict[int, list[MemberHistory]] = {}
    for h in all_history:
        by_member.setdefault(h.member_id, []).append(h)

    events = []
    for member_id, history in by_member.items():
        member = session.get(Member, member_id)
        current_snapshot = (
            json.loads(member_to_snapshot(member)) if member else None)
        for i, h in enumerate(history):
            try:
                snap_before = json.loads(h.snapshot) if h.snapshot else {}
            except Exception:
                snap_before = {}
            if i > 0:
                try:
                    snap_after = json.loads(history[i - 1].snapshot) if history[i - 1].snapshot else {}
                except Exception:
                    snap_after = {}
            elif current_snapshot is not None:
                snap_after = current_snapshot
            else:
                continue

            # 一括変更モード中の記録は差分の連続性を保つため計算には使うが、
            # 一覧には出さない（重要な変更が一括登録で埋もれないようにする）。
            if h.exclude_from_recent:
                continue

            changes = diff_snapshots(snap_before, snap_after)
            if not changes:
                continue
            org_name = (snap_after.get("organization_name")
                       or snap_before.get("organization_name") or "")
            events.append({
                "changed_at": h.changed_at,
                "changed_by": h.changed_by or "",
                "member_id": member_id,
                "org_name": org_name,
                "changes": changes,
            })

    events.sort(key=lambda e: e["changed_at"] or datetime.min, reverse=True)
    return events[:limit]


def get_import_batches(session: Session) -> list:
    """インポートバッチ一覧を新しい順で返す。各行: (batch_id, imported_at, imported_by, count)"""
    return (
        session.query(
            MemberHistory.import_batch_id,
            func.min(MemberHistory.changed_at).label("imported_at"),
            func.min(MemberHistory.changed_by).label("imported_by"),
            func.count(MemberHistory.id).label("count"),
        )
        .filter(MemberHistory.import_batch_id.isnot(None))
        .group_by(MemberHistory.import_batch_id)
        .order_by(func.min(MemberHistory.changed_at).desc())
        .all()
    )


def revert_import_batch(session: Session, batch_id: str) -> dict:
    """指定インポートバッチを取り消す。新規作成会員は削除、更新会員は変更前に戻す。"""
    records = (session.query(MemberHistory)
               .filter_by(import_batch_id=batch_id).all())
    reverted = deleted = 0

    for hist in records:
        member = session.get(Member, hist.member_id)
        if member is None:
            continue

        pre_existing = (
            session.query(MemberHistory)
            .filter(
                MemberHistory.member_id == hist.member_id,
                MemberHistory.import_batch_id != batch_id,
            ).count()
        )

        if pre_existing == 0:
            # インポートで新規作成された会員 → 削除（cascade で履歴も消える）
            session.delete(member)
            deleted += 1
        else:
            # インポートで更新された会員 → スナップショット（変更前）に復元
            data = json.loads(hist.snapshot)
            member.organization_name = data["organization_name"]
            member.organization_kana = data.get("organization_kana", "")
            member.title = data.get("title", "")
            member.name = data["name"]
            member.name_kana = data.get("name_kana", "")
            member.notes = data.get("notes", "")
            member.is_active = data.get("is_active", True)
            member.updated_at = datetime.now()
            pos_name = data.get("position_name", "")
            if pos_name:
                pos = session.query(Position).filter_by(name=pos_name).first()
                member.position_id = pos.id if pos else None
            else:
                member.position_id = None
            session.query(EmailAddress).filter_by(member_id=member.id).delete()
            for ea in data.get("email_addresses", []):
                session.add(EmailAddress(
                    member_id=member.id,
                    address=ea["address"],
                    label=ea.get("label", ""),
                    sort_order=ea.get("sort_order", 1),
                ))
            session.delete(hist)
            reverted += 1

    session.commit()
    return {"reverted": reverted, "deleted": deleted}
