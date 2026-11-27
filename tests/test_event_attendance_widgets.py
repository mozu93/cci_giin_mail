from datetime import date, timedelta

from PyQt6.QtWidgets import QCheckBox

from app.services.meeting_service import (
    KIND_EVENT, create_meeting, get_attendance_data,
)
from app.services.member_service import create_member

_FUTURE = date.today() + timedelta(days=30)


def _setup(db_session, monkeypatch):
    monkeypatch.setattr(
        "app.ui.meeting_widgets.preentry_widget.get_session", lambda: db_session)
    monkeypatch.setattr(
        "app.ui.meeting_widgets.reception_widget.get_session", lambda: db_session)
    member = create_member(db_session, "A-001", "○○商事", "山田太郎")
    ev = create_meeting(db_session, "懇親会", _FUTURE, kind=KIND_EVENT)
    return member, ev


def test_preentry_event_uses_checkbox(qtbot, db_session, monkeypatch):
    from app.ui.meeting_widgets.preentry_widget import PreentryWidget, _STATUS_COL
    member, ev = _setup(db_session, monkeypatch)
    w = PreentryWidget()
    qtbot.addWidget(w)
    w.load(ev.id)

    holder = w._pre_table.cellWidget(0, _STATUS_COL)
    cb = holder.findChild(QCheckBox)
    assert cb is not None
    assert w._pre_table.isColumnHidden(_STATUS_COL + 1)
    assert not w._btn_mail_import.isEnabled()

    cb.setChecked(True)
    d = get_attendance_data(db_session, ev.id)[0]
    assert d["status"] == "出席" and d["actual_status"] == "出席"
    assert w._lbl_total.text() == "合計: 1"

    cb.setChecked(False)
    d = get_attendance_data(db_session, ev.id)[0]
    assert d["status"] == "未回答" and d["actual_status"] == ""


def test_reception_event_checkbox_reflects_preentry(qtbot, db_session, monkeypatch):
    from app.ui.meeting_widgets.reception_widget import (
        ReceptionWidget, _REC_ACTUAL_COL, _REC_PROXY_COL,
    )
    from app.services.meeting_service import set_event_attendance
    member, ev = _setup(db_session, monkeypatch)
    set_event_attendance(db_session, ev.id, member.id, True)
    w = ReceptionWidget(staff_name="担当者A")
    qtbot.addWidget(w)
    w.load(ev.id)

    cb = w._rec_table.cellWidget(0, _REC_ACTUAL_COL).findChild(QCheckBox)
    assert cb.isChecked()
    assert w._rec_table.isColumnHidden(_REC_PROXY_COL)

    cb.setChecked(False)
    d = get_attendance_data(db_session, ev.id)[0]
    assert d["status"] == "未回答" and d["actual_status"] == ""
