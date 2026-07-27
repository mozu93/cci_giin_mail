from datetime import date, timedelta
from app.services.meeting_service import create_meeting, upsert_attendance, update_actual_status
from app.services.member_service import create_member
from app.services.position_service import create_position

_FUTURE_DATE = date.today() + timedelta(days=30)


def test_preentry_summary_resets_to_zero_when_meeting_cleared(qtbot, db_session, monkeypatch):
    """会議削除等でmeeting_idがNoneになった際、事前入力タブの集計バー
    （出席・代理・委任・欠席・未回答・合計）が0にリセットされること。"""
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
    assert w._lbl_attend.text() == "出席: 1"
    assert w._lbl_total.text() == "合計: 1"

    w.load(None)

    assert w._lbl_attend.text() == "出席: 0"
    assert w._lbl_proxy.text() == "代理: 0"
    assert w._lbl_delegate.text() == "委任: 0"
    assert w._lbl_absent.text() == "欠席: 0"
    assert w._lbl_unanswered.text() == "未回答: 0"
    assert w._lbl_total.text() == "合計: 0"
    assert w._pre_table.rowCount() == 0


def test_reception_summary_resets_to_zero_when_meeting_cleared(qtbot, db_session, monkeypatch):
    """会議削除等でmeeting_idがNoneになった際、当日受付タブの集計バーが
    0にリセットされること。"""
    monkeypatch.setattr(
        "app.ui.meeting_widgets.reception_widget.get_session", lambda: db_session)
    position = create_position(db_session, "議員", 1)
    member = create_member(
        db_session, "A-002", "○○商事", "鈴木花子", position_id=position.id)
    meeting = create_meeting(db_session, "常議員会", _FUTURE_DATE)
    upsert_attendance(db_session, meeting.id, member.id, "出席")
    update_actual_status(db_session, meeting.id, member.id, "出席")

    from app.ui.meeting_widgets.reception_widget import ReceptionWidget
    w = ReceptionWidget(staff_name="担当者A")
    qtbot.addWidget(w)
    w.load(meeting.id)
    assert w._lbl_attend.text() == "出席: 1"
    assert w._lbl_total.text() == "合計: 1"

    w.load(None)

    assert w._lbl_attend.text() == "出席: 0"
    assert w._lbl_proxy.text() == "代理: 0"
    assert w._lbl_delegate.text() == "委任: 0"
    assert w._lbl_absent.text() == "欠席: 0"
    assert w._lbl_pending.text() == "未受付: 0"
    assert w._lbl_total.text() == "合計: 0"
    assert w._rec_table.rowCount() == 0
