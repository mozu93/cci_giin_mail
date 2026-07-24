from datetime import date, timedelta
from PyQt6.QtCore import QPoint, QPointF, Qt
from PyQt6.QtGui import QWheelEvent
from PyQt6.QtWidgets import QMessageBox
from app.services.meeting_service import create_meeting, upsert_attendance
from app.services.member_service import create_member, update_member
from app.services.position_service import create_position
from app.services.reception_log_service import create_log

_FUTURE_DATE = date.today() + timedelta(days=30)


def _make_wheel_event() -> QWheelEvent:
    return QWheelEvent(
        QPointF(10, 10), QPointF(10, 10),
        QPoint(0, 0), QPoint(0, 120),
        Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.NoScrollPhase, False,
    )


def test_preentry_status_combo_ignores_wheel_scroll(qtbot, db_session, monkeypatch):
    monkeypatch.setattr(
        "app.ui.meeting_widgets.preentry_widget.get_session", lambda: db_session)
    position = create_position(db_session, "議員", 1)
    member = create_member(
        db_session, "A-001", "○○商事", "山田太郎", position_id=position.id)
    meeting = create_meeting(db_session, "常議員会", _FUTURE_DATE)
    upsert_attendance(db_session, meeting.id, member.id, "出席")

    from app.ui.meeting_widgets.preentry_widget import PreentryWidget
    w = PreentryWidget(readonly=False)
    qtbot.addWidget(w)
    w.load(meeting.id)

    combo = w._pre_table.cellWidget(0, 5)
    before = combo.currentText()
    event = _make_wheel_event()
    combo.wheelEvent(event)

    assert combo.currentText() == before
    assert event.isAccepted() is False


def test_meeting_tab_combo_ignores_wheel_scroll(qtbot, db_session, monkeypatch):
    monkeypatch.setattr(
        "app.ui.meeting_tab.get_session", lambda: db_session)
    create_meeting(db_session, "常議員会", _FUTURE_DATE)

    from app.ui.meeting_tab import MeetingTab
    tab = MeetingTab(staff_name="担当者A")
    qtbot.addWidget(tab)

    before = tab._meeting_combo.currentIndex()
    event = _make_wheel_event()
    tab._meeting_combo.wheelEvent(event)

    assert tab._meeting_combo.currentIndex() == before
    assert event.isAccepted() is False


def test_delete_last_meeting_does_not_crash_and_clears_widgets(
        qtbot, db_session, monkeypatch):
    """最後の1件の会議を削除してもクラッシュせず、事前登録/受付タブの
    表示もクリアされること（reception_logs孤立によるFK違反の回帰確認）。"""
    monkeypatch.setattr(
        "app.ui.meeting_tab.get_session", lambda: db_session)
    monkeypatch.setattr(
        "app.ui.meeting_widgets.preentry_widget.get_session", lambda: db_session)
    monkeypatch.setattr(
        "app.ui.meeting_widgets.reception_widget.get_session", lambda: db_session)
    monkeypatch.setattr(QMessageBox, "question",
                        staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes))

    position = create_position(db_session, "議員", 1)
    member = create_member(
        db_session, "A-301", "○○商事", "受付太郎", position_id=position.id)
    meeting = create_meeting(db_session, "定例会議", _FUTURE_DATE)
    upsert_attendance(db_session, meeting.id, member.id, "出席")
    create_log(db_session, meeting.id, member.id, "担当者A", "", "出席")

    from app.ui.meeting_tab import MeetingTab
    tab = MeetingTab(staff_name="担当者A")
    qtbot.addWidget(tab)
    assert tab._current_meeting_id == meeting.id

    tab._delete_meeting()

    assert tab._current_meeting_id is None
    assert tab._preentry._meeting_id is None
    assert tab._reception._meeting_id is None
    assert tab._preentry._pre_table.rowCount() == 0


def test_meeting_tab_refresh_reflects_member_roster_updates(
        qtbot, db_sessionmaker, monkeypatch):
    """名簿管理タブで会員情報を更新後、会議管理タブへ戻ると（refresh()で）
    最新の名簿データが会議の出欠一覧に反映されること。
    get_session()は呼び出しごとに新しいセッションを返す実運用と同じ状況を再現する。"""
    SessionLocal = db_sessionmaker

    setup_session = SessionLocal()
    position = create_position(setup_session, "議員", 1)
    member = create_member(
        setup_session, "A-401", "変更前商事", "山田太郎", position_id=position.id)
    meeting = create_meeting(setup_session, "定例会議", _FUTURE_DATE)
    upsert_attendance(setup_session, meeting.id, member.id, "出席")
    member_id, meeting_id = member.id, meeting.id
    setup_session.close()

    monkeypatch.setattr(
        "app.ui.meeting_tab.get_session", lambda: SessionLocal())
    monkeypatch.setattr(
        "app.ui.meeting_widgets.preentry_widget.get_session", lambda: SessionLocal())
    monkeypatch.setattr(
        "app.ui.meeting_widgets.reception_widget.get_session", lambda: SessionLocal())

    from app.ui.meeting_tab import MeetingTab
    tab = MeetingTab(staff_name="担当者A")
    qtbot.addWidget(tab)
    assert tab._current_meeting_id == meeting_id
    assert tab._preentry._pre_table.item(0, 1).text() == "変更前商事"

    # 名簿管理タブ側で事業所名を更新（会議管理タブはまだ古い表示のまま）
    update_session = SessionLocal()
    update_member(update_session, member_id, "担当者A", "事業所名変更",
                  organization_name="変更後商事")
    update_session.close()
    assert tab._preentry._pre_table.item(0, 1).text() == "変更前商事"

    # 会議管理タブに戻る（main_windowのタブ切替でrefresh()が呼ばれる想定）
    tab.refresh()

    assert tab._preentry._pre_table.item(0, 1).text() == "変更後商事"
