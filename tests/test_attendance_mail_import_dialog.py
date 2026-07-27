from datetime import date, datetime
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
        lambda graph_config, folder, subject, exclude_ids, since: [
            {"id": "msg-1", "body_text": (
                "【出　　欠】出席\n【事業所名】○○商事\n【氏　　名】山田太郎\n"
                "【代理者名】\n【代理役職】\n【備考】"),
             "received_at": datetime(2026, 7, 10)},
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
        lambda graph_config, folder, subject, exclude_ids, since: [
            {"id": "msg-1", "body_text": (
                "【出　　欠】出席\n【事業所名】存在しない会社\n【氏　　名】不明\n"
                "【代理者名】\n【代理役職】\n【備考】"),
             "received_at": datetime(2026, 7, 10)},
        ])

    from app.ui.dialogs.attendance_mail_import_dialog import AttendanceMailImportDialog
    dlg = AttendanceMailImportDialog(meeting_id=meeting.id, graph_config={})
    qtbot.addWidget(dlg)
    dlg._search()

    combo = dlg._table.cellWidget(0, dlg._COL_MEMBER)
    assert combo.currentData() is None


def test_search_status_label_breaks_down_matched_and_unresolved_counts(
        qtbot, monkeypatch, db_session):
    """読み込み件数の内訳（自動マッチング／要確認／事業所名を読み取れなかった件数）
    を表示し、件数の食い違いに気づけるようにする。"""
    monkeypatch.setattr(
        "app.ui.dialogs.attendance_mail_import_dialog.get_session",
        lambda: db_session)
    create_member(db_session, "A-001", "○○商事", "山田太郎")
    meeting = create_meeting(db_session, "常議員会", date(2026, 7, 20))

    monkeypatch.setattr(
        "app.ui.dialogs.attendance_mail_import_dialog.fetch_messages",
        lambda graph_config, folder, subject, exclude_ids, since: [
            {"id": "msg-1", "body_text": (
                "【出　　欠】出席\n【事業所名】○○商事\n【氏　　名】山田太郎\n"
                "【代理者名】\n【代理役職】\n【備考】"),
             "received_at": datetime(2026, 7, 10)},
            {"id": "msg-2", "body_text": (
                "【出　　欠】欠席\n【事業所名】存在しない会社\n【氏　　名】不明\n"
                "【代理者名】\n【代理役職】\n【備考】"),
             "received_at": datetime(2026, 7, 10)},
            {"id": "msg-3", "body_text": "本文の形式が想定と異なるメール",
             "received_at": datetime(2026, 7, 11)},
        ])

    from app.ui.dialogs.attendance_mail_import_dialog import AttendanceMailImportDialog
    dlg = AttendanceMailImportDialog(meeting_id=meeting.id, graph_config={})
    qtbot.addWidget(dlg)
    dlg._search()

    assert dlg._table.rowCount() == 3
    text = dlg._status_label.text()
    assert "3 件のメールを読み込みました" in text
    assert "自動マッチング 1 件" in text
    assert "要確認 2 件" in text
    assert "うち 1 件は事業所名を読み取れませんでした" in text


def test_apply_completion_message_flags_duplicate_member_matches(
        qtbot, monkeypatch, db_session):
    """表記違いの複数メールが同じ会員に反映された場合、完了メッセージで
    「読み込み件数」と「実際の会員数」の食い違いとその内訳が分かること。"""
    monkeypatch.setattr(
        "app.ui.dialogs.attendance_mail_import_dialog.get_session",
        lambda: db_session)
    member = create_member(db_session, "A-001", "中部電力パワーグリッド株式会社", "鈴木一郎")
    meeting = create_meeting(db_session, "常議員会", date(2026, 7, 20))

    monkeypatch.setattr(
        "app.ui.dialogs.attendance_mail_import_dialog.fetch_messages",
        lambda graph_config, folder, subject, exclude_ids, since: [
            {"id": "msg-1", "body_text": (
                "【出　　欠】出席\n【事業所名】中部電力パワーグリッド株式会社\n"
                "【氏　　名】鈴木一郎\n【代理者名】\n【代理役職】\n【備考】"),
             "received_at": datetime(2026, 7, 10, 9, 0, 0)},
            {"id": "msg-2", "body_text": (
                "【出　　欠】出席\n【事業所名】中部電力パワーグリッド株式会社　四日市支社\n"
                "【氏　　名】鈴木一郎\n【代理者名】\n【代理役職】\n【備考】"),
             "received_at": datetime(2026, 7, 10, 10, 0, 0)},
        ])

    from app.ui.dialogs.attendance_mail_import_dialog import AttendanceMailImportDialog
    dlg = AttendanceMailImportDialog(meeting_id=meeting.id, graph_config={})
    qtbot.addWidget(dlg)
    dlg._search()
    assert dlg._table.rowCount() == 2

    # 2行とも手動で同じ会員を選択（表記違いのため自動マッチングされない想定）
    for r in range(2):
        combo = dlg._table.cellWidget(r, dlg._COL_MEMBER)
        combo.setCurrentIndex(combo.findData(member.id))

    captured = {}

    def fake_information(parent, title, text):
        captured["title"] = title
        captured["text"] = text

    monkeypatch.setattr(QMessageBox, "information", staticmethod(fake_information))

    dlg._apply()

    assert "反映: 2 件" in captured["text"]
    assert "実際の会員数は 1 件です" in captured["text"]
    assert "中部電力パワーグリッド株式会社" in captured["text"]


def test_apply_commits_only_selected_rows(qtbot, monkeypatch, db_session):
    monkeypatch.setattr(
        "app.ui.dialogs.attendance_mail_import_dialog.get_session",
        lambda: db_session)
    member = create_member(db_session, "A-001", "○○商事", "山田太郎")
    meeting = create_meeting(db_session, "常議員会", date(2026, 7, 20))

    monkeypatch.setattr(
        "app.ui.dialogs.attendance_mail_import_dialog.fetch_messages",
        lambda graph_config, folder, subject, exclude_ids, since: [
            {"id": "msg-1", "body_text": (
                "【出　　欠】出席\n【事業所名】○○商事\n【氏　　名】山田太郎\n"
                "【代理者名】\n【代理役職】\n【備考】"),
             "received_at": datetime(2026, 7, 10)},
            {"id": "msg-2", "body_text": (
                "【出　　欠】欠席\n【事業所名】存在しない会社\n【氏　　名】不明\n"
                "【代理者名】\n【代理役職】\n【備考】"),
             "received_at": datetime(2026, 7, 10)},
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
        lambda graph_config, folder, subject, exclude_ids, since: [
            {"id": "msg-1", "body_text": (
                "【出　　欠】出席\n【事業所名】○○商事\n【氏　　名】山田太郎\n"
                "【代理者名】\n【代理役職】\n【備考】"),
             "received_at": datetime(2026, 7, 10)},
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


def test_search_survives_session_close_before_table_refresh(qtbot, monkeypatch, db_sessionmaker):
    session = db_sessionmaker()
    monkeypatch.setattr(
        "app.ui.dialogs.attendance_mail_import_dialog.get_session",
        lambda: db_sessionmaker())
    member = create_member(session, "A-001", "○○商事", "山田太郎")
    meeting = create_meeting(session, "常議員会", date(2026, 7, 20))
    # id を先に確保しておく。create_member/create_meeting はcommitするため、
    # session.close()後にORM属性へアクセスすると(expire_on_commitにより)
    # DetachedInstanceErrorになり、_searchの修正とは無関係な箇所で
    # テストが失敗してしまう。
    member_id = member.id
    meeting_id = meeting.id
    session.close()

    monkeypatch.setattr(
        "app.ui.dialogs.attendance_mail_import_dialog.fetch_messages",
        lambda graph_config, folder, subject, exclude_ids, since: [
            {"id": "msg-1", "body_text": (
                "【出　　欠】出席\n【事業所名】○○商事\n【氏　　名】山田太郎\n"
                "【代理者名】\n【代理役職】\n【備考】"),
             "received_at": datetime(2026, 7, 10)},
        ])

    from app.ui.dialogs.attendance_mail_import_dialog import AttendanceMailImportDialog
    dlg = AttendanceMailImportDialog(meeting_id=meeting_id, graph_config={})
    qtbot.addWidget(dlg)

    dlg._search()  # get_session() called inside _search returns a FRESH session each
                    # time (matching production get_session() semantics), which _search
                    # closes in its own finally block before returning — this test fails
                    # with DetachedInstanceError if _refresh_table runs after that close
    combo = dlg._table.cellWidget(0, dlg._COL_MEMBER)
    assert combo.currentData() == member_id
