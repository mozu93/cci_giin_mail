from datetime import date

from PyQt6.QtWidgets import QMessageBox, QInputDialog

from app.database.models import ReceptionLog, AttendanceRecord, Meeting, SendJob, SendLog
from app.services.committee_service import get_committees, create_committee
from app.services.position_service import get_positions, create_position
from app.services.member_service import create_member, get_members
from app.services.meeting_service import create_meeting, upsert_attendance
from app.services.reception_log_service import create_log
from app.services.send_job_service import create_job, add_log


def _confirm(monkeypatch):
    monkeypatch.setattr(
        QMessageBox, "warning",
        staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes))
    monkeypatch.setattr(
        QInputDialog, "getText",
        staticmethod(lambda *a, **k: ("DELETE", True)))
    monkeypatch.setattr(
        QMessageBox, "information",
        staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(
        QMessageBox, "critical",
        staticmethod(lambda *a, **k: None))


def test_bulk_delete_also_clears_positions_and_committees(
        qtbot, monkeypatch, db_session):
    monkeypatch.setattr("app.ui.settings_tab.get_session", lambda: db_session)
    _confirm(monkeypatch)

    committee = create_committee(db_session, "総務委員会", 1)
    position = create_position(db_session, "議員", 1)
    create_member(
        db_session, "A-001", "○○商事", "山田太郎",
        committee_id=committee.id, position_id=position.id)

    from app.ui.settings_tab import _DataWidget
    w = _DataWidget()
    qtbot.addWidget(w)
    w._bulk_delete()

    assert get_members(db_session, active_only=False) == []
    assert get_committees(db_session) == []
    assert get_positions(db_session) == []


def test_bulk_delete_also_clears_meetings_attendance_and_send_history(
        qtbot, monkeypatch, db_session):
    monkeypatch.setattr("app.ui.settings_tab.get_session", lambda: db_session)
    _confirm(monkeypatch)

    member = create_member(db_session, "A-001", "○○商事", "山田太郎")
    meeting = create_meeting(db_session, "定例会議", date(2026, 7, 1))
    upsert_attendance(db_session, meeting.id, member.id, "出席")
    create_log(db_session, meeting.id, member.id, "担当者A", "未回答", "出席")
    job = create_job(db_session, "テスト送信", template_id=None, staff_id=None)
    add_log(db_session, job.id, member.id, "a@example.com", "件名", "success")

    from app.ui.settings_tab import _DataWidget
    w = _DataWidget()
    qtbot.addWidget(w)
    w._bulk_delete()

    assert get_members(db_session, active_only=False) == []
    assert db_session.query(Meeting).all() == []
    assert db_session.query(AttendanceRecord).all() == []
    assert db_session.query(ReceptionLog).all() == []
    assert db_session.query(SendJob).all() == []
    assert db_session.query(SendLog).all() == []


def test_bulk_delete_cancelled_keeps_positions_and_committees(
        qtbot, monkeypatch, db_session):
    monkeypatch.setattr("app.ui.settings_tab.get_session", lambda: db_session)
    monkeypatch.setattr(
        QMessageBox, "warning",
        staticmethod(lambda *a, **k: QMessageBox.StandardButton.No))
    monkeypatch.setattr(
        QMessageBox, "information",
        staticmethod(lambda *a, **k: None))

    create_committee(db_session, "総務委員会", 1)
    create_position(db_session, "議員", 1)

    from app.ui.settings_tab import _DataWidget
    w = _DataWidget()
    qtbot.addWidget(w)
    w._bulk_delete()

    assert len(get_committees(db_session)) == 1
    assert len(get_positions(db_session)) == 1
