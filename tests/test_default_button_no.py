import pytest
from PyQt6.QtWidgets import QMessageBox


@pytest.fixture
def capture_question(monkeypatch):
    calls = []

    def fake_question(*args, **kwargs):
        calls.append((args, kwargs))
        return QMessageBox.StandardButton.No

    monkeypatch.setattr(QMessageBox, "question", staticmethod(fake_question))
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(fake_question))
    return calls


def _default_button_arg(args, kwargs):
    if "defaultButton" in kwargs:
        return kwargs["defaultButton"]
    return args[4] if len(args) > 4 else None


def test_meeting_delete_defaults_to_no(qtbot, monkeypatch, capture_question):
    # Mock _load_meetings to avoid database setup
    monkeypatch.setattr("app.ui.meeting_tab.MeetingTab._load_meetings", lambda self: None)
    from app.ui.meeting_tab import MeetingTab
    tab = MeetingTab()
    qtbot.addWidget(tab)

    # Set up meeting combo to have a selection
    tab._meeting_combo.addItem("Test Meeting", 1)
    tab._current_meeting_id = 1

    # Call delete and check the message box call
    tab._delete_meeting()
    assert capture_question, "QMessageBox.question が呼ばれていない"
    args, kwargs = capture_question[0]
    assert _default_button_arg(args, kwargs) == QMessageBox.StandardButton.No
