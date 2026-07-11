from PyQt6.QtWidgets import QTextEdit


def test_body_field_is_textedit_and_preserves_newlines(qtbot, monkeypatch):
    monkeypatch.setattr(
        "app.ui.settings_tab.get_session", lambda: _FakeSession())
    monkeypatch.setattr("app.ui.settings_tab.get_signatures", lambda s, sid: [])

    from app.ui.settings_tab import _SignatureWidget
    w = _SignatureWidget(staff_id=1)
    qtbot.addWidget(w)

    assert isinstance(w._body, QTextEdit)
    w._body.setPlainText("1行目\n2行目\n3行目")
    assert w._body.toPlainText() == "1行目\n2行目\n3行目"


class _FakeSession:
    def close(self):
        pass
