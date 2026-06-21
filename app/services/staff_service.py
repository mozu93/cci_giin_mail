from sqlalchemy.orm import Session
from app.database.models import Staff


def create_staff(session: Session, name: str) -> Staff:
    s = Staff(name=name, is_active=True)
    session.add(s)
    session.commit()
    return s


def get_active_staff(session: Session) -> list[Staff]:
    return (session.query(Staff)
            .filter_by(is_active=True)
            .order_by(Staff.name)
            .all())


def get_all_staff(session: Session) -> list[Staff]:
    return session.query(Staff).order_by(Staff.name).all()


def set_active(session: Session, staff_id: int, is_active: bool) -> None:
    s = session.get(Staff, staff_id)
    if s:
        s.is_active = is_active
        session.commit()
