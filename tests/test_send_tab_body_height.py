from PyQt6.QtWidgets import QTextEdit, QDialog


def test_body_edit_has_expand_button(qtbot, monkeypatch):
    monkeypatch.setattr("app.ui.send_tab.get_session", lambda: _FakeSession())
    monkeypatch.setattr("app.ui.send_tab.get_positions", lambda s: [])
    monkeypatch.setattr("app.ui.send_tab.get_committees", lambda s: [])
    monkeypatch.setattr("app.ui.send_tab.get_members", lambda s: [])
    monkeypatch.setattr("app.ui.send_tab.get_templates", lambda s: [])
    monkeypatch.setattr("app.ui.send_tab.get_signatures", lambda s: [])
    monkeypatch.setattr("app.ui.send_tab.get_default_signature", lambda s: None)

    from app.ui.send_tab import SendTab
    tab = SendTab()
    qtbot.addWidget(tab)

    assert tab._body_edit.maximumHeight() >= 240
    assert hasattr(tab, "_btn_expand_body")


def test_expand_body_edit_accept(qtbot, monkeypatch):
    """Test that accepting the expand dialog copies new text back to _body_edit."""
    monkeypatch.setattr("app.ui.send_tab.get_session", lambda: _FakeSession())
    monkeypatch.setattr("app.ui.send_tab.get_positions", lambda s: [])
    monkeypatch.setattr("app.ui.send_tab.get_committees", lambda s: [])
    monkeypatch.setattr("app.ui.send_tab.get_members", lambda s: [])
    monkeypatch.setattr("app.ui.send_tab.get_templates", lambda s: [])
    monkeypatch.setattr("app.ui.send_tab.get_signatures", lambda s: [])
    monkeypatch.setattr("app.ui.send_tab.get_default_signature", lambda s: None)

    from app.ui.send_tab import SendTab

    # Monkeypatch QDialog.exec to simulate user editing and accepting
    def mock_exec(self):
        # Find the internal QTextEdit in the dialog
        editor = self.findChild(QTextEdit)
        if editor:
            # Simulate user editing: replace text
            editor.setPlainText("Modified text from dialog")
        # Return truthy value (1 = accepted)
        return 1

    monkeypatch.setattr(QDialog, "exec", mock_exec)

    tab = SendTab()
    qtbot.addWidget(tab)

    # Set initial text in the main body edit
    tab._body_edit.setPlainText("Original text")

    # Call _expand_body_edit which should open the dialog
    tab._expand_body_edit()

    # Verify the text was synced from the dialog back to _body_edit
    assert tab._body_edit.toPlainText() == "Modified text from dialog"


def test_expand_body_edit_cancel(qtbot, monkeypatch):
    """Test that canceling the expand dialog leaves _body_edit unchanged."""
    monkeypatch.setattr("app.ui.send_tab.get_session", lambda: _FakeSession())
    monkeypatch.setattr("app.ui.send_tab.get_positions", lambda s: [])
    monkeypatch.setattr("app.ui.send_tab.get_committees", lambda s: [])
    monkeypatch.setattr("app.ui.send_tab.get_members", lambda s: [])
    monkeypatch.setattr("app.ui.send_tab.get_templates", lambda s: [])
    monkeypatch.setattr("app.ui.send_tab.get_signatures", lambda s: [])
    monkeypatch.setattr("app.ui.send_tab.get_default_signature", lambda s: None)

    from app.ui.send_tab import SendTab

    # Monkeypatch QDialog.exec to simulate user canceling
    def mock_exec(self):
        # Don't modify the dialog; just reject it
        # Return falsy value (0 = rejected)
        return 0

    monkeypatch.setattr(QDialog, "exec", mock_exec)

    tab = SendTab()
    qtbot.addWidget(tab)

    # Set initial text in the main body edit
    original_text = "Text that should not change"
    tab._body_edit.setPlainText(original_text)

    # Call _expand_body_edit which should open the dialog
    tab._expand_body_edit()

    # Verify the text was NOT changed
    assert tab._body_edit.toPlainText() == original_text


class _FakeSession:
    def close(self):
        pass
