from datetime import datetime, timedelta
from app.database.models import EmailTemplate, Staff, SendJob, SendLog
from app.services.send_job_service import (
    create_job, start_job, finish_job, add_log,
    get_jobs, get_job_logs, delete_old_jobs
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


def test_delete_old_jobs_removes_jobs_older_than_one_year(db_session):
    tmpl, staff = _setup(db_session)
    old_job = create_job(db_session, "1年以上前のジョブ", tmpl.id, staff.id)
    old_job.sent_at = datetime.now() - timedelta(days=366)
    db_session.commit()

    deleted_count = delete_old_jobs(db_session, days=365)

    assert deleted_count == 1
    assert db_session.get(SendJob, old_job.id) is None


def test_delete_old_jobs_keeps_jobs_within_one_year(db_session):
    tmpl, staff = _setup(db_session)
    recent_job = create_job(db_session, "364日前のジョブ", tmpl.id, staff.id)
    recent_job.sent_at = datetime.now() - timedelta(days=364)
    db_session.commit()

    deleted_count = delete_old_jobs(db_session, days=365)

    assert deleted_count == 0
    assert db_session.get(SendJob, recent_job.id) is not None


def test_delete_old_jobs_keeps_drafts_without_sent_at(db_session):
    tmpl, staff = _setup(db_session)
    draft_job = create_job(db_session, "下書きジョブ", tmpl.id, staff.id)
    # sent_atはNoneのまま(create_jobはsent_atを設定しない)

    deleted_count = delete_old_jobs(db_session, days=365)

    assert deleted_count == 0
    assert db_session.get(SendJob, draft_job.id) is not None


def test_delete_old_jobs_cascades_to_logs(db_session):
    tmpl, staff = _setup(db_session)
    old_job = create_job(db_session, "1年以上前のジョブ", tmpl.id, staff.id)
    log = add_log(db_session, old_job.id, None, "a@example.com", "件名", "success")
    old_job.sent_at = datetime.now() - timedelta(days=400)
    db_session.commit()
    log_id = log.id

    delete_old_jobs(db_session, days=365)

    assert db_session.get(SendLog, log_id) is None
