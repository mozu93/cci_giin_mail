from datetime import date
from app.services.meeting_service import create_meeting
from app.services.member_service import create_member
from app.database.models import ProcessedAttendanceMail, AttendanceRecord
from PyQt6.QtCore import Qt, QPoint, QPointF
from PyQt6.QtGui import QWheelEvent
from PyQt6.QtWidgets import QMessageBox


def test_search_populates_table_with_matched_member_preselected(
        qtbot, monkeypatch, db_session):
    monkeypatch.setattr(
        "app.ui.dialogs.attendance_mail_import_dialog.get_session",
        lambda: db_session)
    member = create_member(db_session, "A-001", "○○商事", "山田太郎")
    meeting = create_meeting(db_session, "常議員会", date(2026, 7, 20))

    monkeypatch.setattr(
        "app.ui.dialogs.attendance_mail_import_dialog.fetch_messages",
        lambda graph_config, folder, subject, exclude_ids: [
            {"id": "msg-1", "body_text": (
                "【出　　欠】出席\n【事業所名】○○商事\n【氏　　名】山田太郎\n"
                "【代理者名】\n【代理役職】\n【備考】")},
        ])

    from app.ui.dialogs.attendance_mail_import_dialog import AttendanceMailImportDialog
    dlg = AttendanceMailImportDialog(meeting_id=meeting.id, graph_config={})
    qtbot.addWidget(dlg)

    dlg._folder_input.setText("常議員会出欠")
    dlg._search()

    assert dlg._table.rowCount() == 1
    combo = dlg._table.cellWidget(0, dlg._COL_MEMBER)
    assert combo.currentData() == member.id


def test_search_leaves_unmatched_row_unselected(qtbot, monkeypatch, db_session):
    monkeypatch.setattr(
        "app.ui.dialogs.attendance_mail_import_dialog.get_session",
        lambda: db_session)
    meeting = create_meeting(db_session, "常議員会", date(2026, 7, 20))

    monkeypatch.setattr(
        "app.ui.dialogs.attendance_mail_import_dialog.fetch_messages",
        lambda graph_config, folder, subject, exclude_ids: [
            {"id": "msg-1", "body_text": (
                "【出　　欠】出席\n【事業所名】存在しない会社\n【氏　　名】不明\n"
                "【代理者名】\n【代理役職】\n【備考】")},
        ])

    from app.ui.dialogs.attendance_mail_import_dialog import AttendanceMailImportDialog
    dlg = AttendanceMailImportDialog(meeting_id=meeting.id, graph_config={})
    qtbot.addWidget(dlg)
    dlg._search()

    combo = dlg._table.cellWidget(0, dlg._COL_MEMBER)
    assert combo.currentData() is None


def test_apply_commits_only_selected_rows(qtbot, monkeypatch, db_session):
    monkeypatch.setattr(
        "app.ui.dialogs.attendance_mail_import_dialog.get_session",
        lambda: db_session)
    member = create_member(db_session, "A-001", "○○商事", "山田太郎")
    meeting = create_meeting(db_session, "常議員会", date(2026, 7, 20))

    monkeypatch.setattr(
        "app.ui.dialogs.attendance_mail_import_dialog.fetch_messages",
        lambda graph_config, folder, subject, exclude_ids: [
            {"id": "msg-1", "body_text": (
                "【出　　欠】出席\n【事業所名】○○商事\n【氏　　名】山田太郎\n"
                "【代理者名】\n【代理役職】\n【備考】")},
            {"id": "msg-2", "body_text": (
                "【出　　欠】欠席\n【事業所名】存在しない会社\n【氏　　名】不明\n"
                "【代理者名】\n【代理役職】\n【備考】")},
        ])

    from app.ui.dialogs.attendance_mail_import_dialog import AttendanceMailImportDialog
    dlg = AttendanceMailImportDialog(meeting_id=meeting.id, graph_config={})
    qtbot.addWidget(dlg)
    dlg._search()

    monkeypatch.setattr(
        QMessageBox, "information",
        staticmethod(lambda *a, **k: None))

    dlg._apply()

    record = (db_session.query(AttendanceRecord)
             .filter_by(meeting_id=meeting.id, member_id=member.id).first())
    assert record.status == "出席"
    assert db_session.query(ProcessedAttendanceMail).count() == 1
    assert db_session.query(ProcessedAttendanceMail).first().message_id == "msg-1"


def test_no_wheel_combo_ignores_wheel_event(qtbot, monkeypatch, db_session):
    monkeypatch.setattr(
        "app.ui.dialogs.attendance_mail_import_dialog.get_session",
        lambda: db_session)
    member = create_member(db_session, "A-001", "○○商事", "山田太郎")
    meeting = create_meeting(db_session, "常議員会", date(2026, 7, 20))

    monkeypatch.setattr(
        "app.ui.dialogs.attendance_mail_import_dialog.fetch_messages",
        lambda graph_config, folder, subject, exclude_ids: [
            {"id": "msg-1", "body_text": (
                "【出　　欠】出席\n【事業所名】○○商事\n【氏　　名】山田太郎\n"
                "【代理者名】\n【代理役職】\n【備考】")},
        ])

    from app.ui.dialogs.attendance_mail_import_dialog import AttendanceMailImportDialog
    dlg = AttendanceMailImportDialog(meeting_id=meeting.id, graph_config={})
    qtbot.addWidget(dlg)
    dlg._search()

    combo = dlg._table.cellWidget(0, dlg._COL_MEMBER)
    before = combo.currentIndex()
    event = QWheelEvent(
        QPointF(0, 0), QPointF(0, 0), QPoint(0, 120), QPoint(0, 120),
        Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.NoScrollPhase, False)
    combo.wheelEvent(event)
    assert combo.currentIndex() == before
