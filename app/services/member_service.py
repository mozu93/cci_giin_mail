import json
from datetime import datetime
from sqlalchemy import func
from sqlalchemy.orm import Session, contains_eager, selectinload
from sqlalchemy.exc import IntegrityError
from app.database.models import Member, EmailAddress, MemberHistory, Position


def member_to_snapshot(member: Member) -> str:
    data = {
        "member_number":     member.member_number,
        "position_name":     member.position.name if member.position else "",
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
                  organization_name: str, name: str, **kwargs) -> Member:
    """会員を作成する。履歴は呼び出し元でメール設定後に record_member_history() で記録すること。"""
    member = Member(
        member_number=member_number,
        organization_name=organization_name,
        name=name,
        **kwargs
    )
    session.add(member)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise
    return member


def record_member_history(session: Session, member_id: int,
                          changed_by: str, change_reason: str) -> None:
    """現在のメンバー状態（メールアドレス含む）をスナップショットとして履歴に記録する。"""
    member = session.get(Member, member_id)
    if member is None:
        return
    session.add(MemberHistory(
        member_id=member_id,
        changed_by=changed_by or "システム",
        change_reason=change_reason,
        snapshot=member_to_snapshot(member),
    ))
    session.commit()


def get_member(session: Session, member_id: int) -> Member | None:
    return session.get(Member, member_id)


def get_members(session: Session, position_id: int | None = None,
                keyword: str | None = None,
                active_only: bool = True) -> list[Member]:
    q = (session.query(Member)
         .outerjoin(Member.position)
         .options(contains_eager(Member.position),
                  selectinload(Member.email_addresses)))
    if active_only:
        q = q.filter(Member.is_active == True)
    if position_id is not None:
        q = q.filter(Member.position_id == position_id)
    if keyword:
        escaped = keyword.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        like = f"%{escaped}%"
        q = q.filter(
            Member.organization_name.like(like, escape="\\") |
            Member.name.like(like, escape="\\") |
            Member.member_number.like(like, escape="\\")
        )
    return q.order_by(
        Position.sort_order.asc().nullslast(),
        Member.display_order.asc().nullslast(),
        Member.organization_kana.asc(),
    ).all()


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
                  changed_by: str, change_reason: str, **kwargs) -> Member:
    member = session.get(Member, member_id)
    if member is None:
        raise ValueError(f"会員ID {member_id} が見つかりません")
    # 変更前のスナップショット（メールアドレス含む）を記録
    snapshot = member_to_snapshot(member)
    session.add(MemberHistory(
        member_id=member_id,
        changed_by=changed_by,
        change_reason=change_reason,
        snapshot=snapshot,
    ))
    for key, value in kwargs.items():
        setattr(member, key, value)
    member.updated_at = datetime.now()
    session.commit()
    return member


def delete_member(session: Session, member_id: int,
                  changed_by: str = "") -> None:
    """退任処理: is_active=Falseに変更し、履歴を保持する"""
    member = session.get(Member, member_id)
    if member:
        session.add(MemberHistory(
            member_id=member_id,
            changed_by=changed_by or "システム",
            change_reason="議員退任",
            snapshot=member_to_snapshot(member),
        ))
        member.is_active = False
        member.updated_at = datetime.now()
        session.commit()


def get_member_history(session: Session, member_id: int) -> list[MemberHistory]:
    return (session.query(MemberHistory)
            .filter_by(member_id=member_id)
            .order_by(MemberHistory.changed_at.desc())
            .all())


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
