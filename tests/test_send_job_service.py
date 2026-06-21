from app.database.models import EmailTemplate, Staff
from app.services.send_job_service import (
    create_job, start_job, finish_job, add_log,
    get_jobs, get_job_logs
)


def _setup(db_session):
    tmpl = EmailTemplate(name="案内", subject="件名", body="本文")
    staff = Staff(name="田中")
    db_session.add_all([tmpl, staff])
    db_session.flush()
    return tmpl, staff


def test_create_job(db_session):
    tmpl, staff = _setup(db_session)
    job = create_job(db_session, "2026年6月 総会案内", tmpl.id, staff.id)
    assert job.id is not None
    assert job.status == "draft"


def test_start_and_finish_job(db_session):
    tmpl, staff = _setup(db_session)
    job = create_job(db_session, "テストジョブ", tmpl.id, staff.id)
    start_job(db_session, job.id)
    db_session.refresh(job)
    assert job.status == "sending"
    finish_job(db_session, job.id)
    db_session.refresh(job)
    assert job.status == "done"
    assert job.sent_at is not None


def test_add_log_and_get(db_session):
    tmpl, staff = _setup(db_session)
    job = create_job(db_session, "テストジョブ", tmpl.id, staff.id)
    add_log(db_session, job.id, None, "a@example.com", "件名", "success")
    add_log(db_session, job.id, None, "b@example.com", "件名", "error",
            error_message="タイムアウト")
    logs = get_job_logs(db_session, job.id)
    assert len(logs) == 2
    errors = [l for l in logs if l.status == "error"]
    assert errors[0].error_message == "タイムアウト"


def test_finish_job_updates_counts(db_session):
    tmpl, staff = _setup(db_session)
    job = create_job(db_session, "テストジョブ", tmpl.id, staff.id)
    start_job(db_session, job.id)
    add_log(db_session, job.id, None, "a@example.com", "件名", "success")
    add_log(db_session, job.id, None, "b@example.com", "件名", "success")
    add_log(db_session, job.id, None, "c@example.com", "件名", "error")
    finish_job(db_session, job.id)
    db_session.refresh(job)
    assert job.total_count == 3
    assert job.success_count == 2
    assert job.error_count == 1
