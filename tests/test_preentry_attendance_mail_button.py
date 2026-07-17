from datetime import date
from app.services.meeting_service import create_meeting


def test_mail_import_button_hidden_when_readonly(qtbot, db_session, monkeypatch):
    monkeypatch.setattr(
        "app.ui.meeting_widgets.preentry_widget.get_session", lambda: db_session)
    from app.ui.meeting_widgets.preentry_widget import PreentryWidget
    w = PreentryWidget(readonly=True)
    qtbot.addWidget(w)
    assert w._btn_mail_import is None


def test_mail_import_button_opens_dialog_and_refreshes(qtbot, db_session, monkeypatch):
    monkeypatch.setattr(
        "app.ui.meeting_widgets.preentry_widget.get_session", lambda: db_session)
    meeting = create_meeting(db_session, "常議員会", date(2026, 7, 20))

    from app.ui.meeting_widgets import preentry_widget as mod

    class _FakeDialog:
        def __init__(self, meeting_id, graph_config, parent=None):
            _FakeDialog.created_with = meeting_id
        def exec(self):
            return 1  # QDialog.DialogCode.Accepted相当

    monkeypatch.setattr(mod, "AttendanceMailImportDialog", _FakeDialog)

    w = mod.PreentryWidget(readonly=False)
    qtbot.addWidget(w)
    w.load(meeting.id)

    reload_called = []
    monkeypatch.setattr(w, "_load_preentry", lambda: reload_called.append(True))

    w._btn_mail_import.click()

    assert _FakeDialog.created_with == meeting.id
    assert reload_called == [True]
