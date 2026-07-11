class _FakeSession:
    def close(self):
        pass


def _patch_common(monkeypatch, test_address=None):
    monkeypatch.setattr("app.ui.send_tab.get_session", lambda: _FakeSession())
    monkeypatch.setattr("app.ui.send_tab.get_positions", lambda s: [])
    monkeypatch.setattr("app.ui.send_tab.get_committees", lambda s: [])
    monkeypatch.setattr("app.ui.send_tab.get_members", lambda s: [])
    monkeypatch.setattr("app.ui.send_tab.get_templates", lambda s: [])
    monkeypatch.setattr("app.ui.send_tab.get_signatures", lambda s: [])
    monkeypatch.setattr("app.ui.send_tab.get_default_signature", lambda s: None)
    monkeypatch.setattr("app.ui.send_tab.get_staff_by_name", lambda s, name: None)
    monkeypatch.setattr(
        "app.ui.send_tab.get_graph_config",
        lambda: {"test_address": test_address} if test_address else {})


def test_button_shows_unset_when_no_test_address(qtbot, monkeypatch):
    _patch_common(monkeypatch, test_address=None)
    from app.ui.send_tab import SendTab
    tab = SendTab(staff_name="担当者A")
    qtbot.addWidget(tab)
    assert tab._btn_test.text() == "テスト送信（未設定）"


def test_button_shows_address_when_configured(qtbot, monkeypatch):
    _patch_common(monkeypatch, test_address="test@example.com")
    from app.ui.send_tab import SendTab
    tab = SendTab(staff_name="担当者A")
    qtbot.addWidget(tab)
    assert tab._btn_test.text() == "test@example.com にテスト送信"


def test_refresh_updates_button_label(qtbot, monkeypatch):
    _patch_common(monkeypatch, test_address=None)
    from app.ui.send_tab import SendTab
    tab = SendTab(staff_name="担当者A")
    qtbot.addWidget(tab)
    assert tab._btn_test.text() == "テスト送信（未設定）"

    monkeypatch.setattr(
        "app.ui.send_tab.get_graph_config",
        lambda: {"test_address": "new@example.com"})
    tab.refresh()
    assert tab._btn_test.text() == "new@example.com にテスト送信"
