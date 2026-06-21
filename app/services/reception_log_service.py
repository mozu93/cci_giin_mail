from sqlalchemy.orm import Session
from app.database.models import ReceptionLog


def create_log(session: Session, meeting_id: int, member_id: int,
               staff_name: str, old_status: str, new_status: str) -> None:
    log = ReceptionLog(
        meeting_id=meeting_id,
        member_id=member_id,
        staff_name=staff_name,
        old_status=old_status,
        new_status=new_status,
    )
    session.add(log)
    session.commit()


def get_logs(session: Session, meeting_id: int) -> list[ReceptionLog]:
    return (
        session.query(ReceptionLog)
        .filter_by(meeting_id=meeting_id)
        .order_by(ReceptionLog.changed_at.desc())
        .all()
    )
