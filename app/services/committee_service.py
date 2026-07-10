from sqlalchemy.orm import Session
from app.database.models import Committee


def create_committee(session: Session, name: str, sort_order: int) -> Committee:
    committee = Committee(name=name, sort_order=sort_order)
    session.add(committee)
    session.commit()
    return committee


def get_committees(session: Session) -> list[Committee]:
    return session.query(Committee).order_by(Committee.sort_order).all()


def update_committee(session: Session, committee_id: int, **kwargs) -> Committee:
    committee = session.get(Committee, committee_id)
    if committee is None:
        raise ValueError(f"委員会ID {committee_id} が見つかりません")
    for k, v in kwargs.items():
        setattr(committee, k, v)
    session.commit()
    return committee


def delete_committee(session: Session, committee_id: int) -> None:
    committee = session.get(Committee, committee_id)
    if committee:
        session.delete(committee)
        session.commit()
