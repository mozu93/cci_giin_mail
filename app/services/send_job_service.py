from datetime import datetime
from sqlalchemy.orm import Session
from app.database.models import SendJob, SendLog


def create_job(session: Session, name: str,
               template_id: int, staff_id: int) -> SendJob:
    job = SendJob(name=name, template_id=template_id,
                  staff_id=staff_id, status="draft")
    session.add(job)
    session.commit()
    return job


def start_job(session: Session, job_id: int) -> None:
    job = session.get(SendJob, job_id)
    if job:
        job.status = "sending"
        session.commit()


def finish_job(session: Session, job_id: int) -> None:
    job = session.get(SendJob, job_id)
    if job is None:
        return
    logs = get_job_logs(session, job_id)
    job.total_count = len(logs)
    job.success_count = sum(1 for l in logs if l.status == "success")
    job.error_count = sum(1 for l in logs if l.status == "error")
    job.status = "done"
    job.sent_at = datetime.now()
    session.commit()


def add_log(session: Session, job_id: int, member_id: int | None,
            to_address: str, subject: str, status: str,
            error_message: str = "") -> SendLog:
    log = SendLog(
        job_id=job_id,
        member_id=member_id,
        to_address=to_address,
        subject=subject,
        status=status,
        error_message=error_message,
        sent_at=datetime.now() if status in ("success", "error") else None,
    )
    session.add(log)
    session.commit()
    return log


def get_jobs(session: Session) -> list[SendJob]:
    return (session.query(SendJob)
            .order_by(SendJob.created_at.desc())
            .all())


def get_job_logs(session: Session, job_id: int) -> list[SendLog]:
    return (session.query(SendLog)
            .filter_by(job_id=job_id)
            .order_by(SendLog.id)
            .all())
