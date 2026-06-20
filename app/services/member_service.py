import json
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.database.models import Member, EmailAddress, MemberHistory


def member_to_snapshot(member: Member) -> str:
    data = {
        "member_number":    member.member_number,
        "position_id":      member.position_id,
        "organization_name": member.organization_name,
        "organization_kana": member.organization_kana,
        "title":            member.title,
        "name":             member.name,
        "name_kana":        member.name_kana,
        "notes":            member.notes,
        "is_active":        member.is_active,
        "email_addresses":  [
            {"address": e.address, "label": e.label, "sort_order": e.sort_order}
            for e in member.email_addresses
        ],
    }
    return json.dumps(data, ensure_ascii=False)


def create_member(session: Session, member_number: str,
                  organization_name: str, name: str, **kwargs) -> Member:
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


def get_member(session: Session, member_id: int) -> Member | None:
    return session.get(Member, member_id)


def get_members(session: Session, position_id: int | None = None,
                keyword: str | None = None,
                active_only: bool = True) -> list[Member]:
    q = session.query(Member)
    if active_only:
        q = q.filter(Member.is_active == True)
    if position_id is not None:
        q = q.filter(Member.position_id == position_id)
    if keyword:
        like = f"%{keyword}%"
        q = q.filter(
            Member.organization_name.like(like) |
            Member.name.like(like) |
            Member.member_number.like(like)
        )
    return q.order_by(Member.member_number).all()


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
    session.flush()


def update_member(session: Session, member_id: int,
                  changed_by: str, change_reason: str, **kwargs) -> Member:
    member = session.get(Member, member_id)
    if member is None:
        raise ValueError(f"会員ID {member_id} が見つかりません")
    snapshot = member_to_snapshot(member)
    history = MemberHistory(
        member_id=member_id,
        changed_by=changed_by,
        change_reason=change_reason,
        snapshot=snapshot,
    )
    session.add(history)
    for key, value in kwargs.items():
        setattr(member, key, value)
    session.commit()
    return member


def delete_member(session: Session, member_id: int) -> None:
    member = session.get(Member, member_id)
    if member:
        session.delete(member)
        session.commit()


def get_member_history(session: Session, member_id: int) -> list[MemberHistory]:
    return (session.query(MemberHistory)
            .filter_by(member_id=member_id)
            .order_by(MemberHistory.changed_at.desc())
            .all())
