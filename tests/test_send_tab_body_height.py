def test_body_edit_has_expand_button(qtbot, monkeypatch):
    monkeypatch.setattr("app.ui.send_tab.get_session", lambda: _FakeSession())
    monkeypatch.setattr("app.ui.send_tab.get_positions", lambda s: [])
    monkeypatch.setattr("app.ui.send_tab.get_members", lambda s: [])
    monkeypatch.setattr("app.ui.send_tab.get_templates", lambda s: [])
    monkeypatch.setattr("app.ui.send_tab.get_signatures", lambda s: [])
    monkeypatch.setattr("app.ui.send_tab.get_default_signature", lambda s: None)

    from app.ui.send_tab import SendTab
    tab = SendTab()
    qtbot.addWidget(tab)

    assert tab._body_edit.maximumHeight() >= 240
    assert hasattr(tab, "_btn_expand_body")


class _FakeSession:
    def close(self):
        pass
