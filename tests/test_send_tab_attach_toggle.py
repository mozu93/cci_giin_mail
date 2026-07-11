class _FakeSession:
    def close(self):
        pass


def _patch_common(monkeypatch):
    monkeypatch.setattr("app.ui.send_tab.get_session", lambda: _FakeSession())
    monkeypatch.setattr("app.ui.send_tab.get_positions", lambda s: [])
    monkeypatch.setattr("app.ui.send_tab.get_committees", lambda s: [])
    monkeypatch.setattr("app.ui.send_tab.get_members", lambda s: [])
    monkeypatch.setattr("app.ui.send_tab.get_templates", lambda s: [])
    monkeypatch.setattr("app.ui.send_tab.get_signatures", lambda s: [])
    monkeypatch.setattr("app.ui.send_tab.get_default_signature", lambda s: None)


def test_attach_body_hidden_until_checked(qtbot, monkeypatch):
    _patch_common(monkeypatch)
    from app.ui.send_tab import SendTab
    tab = SendTab(staff_name="担当者A")
    qtbot.addWidget(tab)
    tab.show()

    assert tab._chk_use_attach.isChecked() is False
    assert tab._attach_body.isVisible() is False

    tab._chk_use_attach.setChecked(True)
    assert tab._attach_body.isVisible() is True


def test_clear_all_resets_attach_checkbox(qtbot, monkeypatch):
    _patch_common(monkeypatch)
    from app.ui.send_tab import SendTab
    tab = SendTab(staff_name="担当者A")
    qtbot.addWidget(tab)
    tab.show()

    tab._chk_use_attach.setChecked(True)
    tab._clear_all()
    assert tab._chk_use_attach.isChecked() is False
    assert tab._attach_body.isVisible() is False
