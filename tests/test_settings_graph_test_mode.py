from app.ui.settings_tab import _GraphSettingsWidget


def test_test_mode_toggle_is_saved_immediately(qtbot, monkeypatch):
    config = {
        "graph": {
            "tenant_id": "tenant",
            "test_address": "tester@example.com",
            "test_mode": False,
        }
    }
    saved = []
    monkeypatch.setattr("app.ui.settings_tab.get_config", lambda: config)
    monkeypatch.setattr(
        "app.ui.settings_tab.save_config",
        lambda value: saved.append(value["graph"].copy()),
    )

    widget = _GraphSettingsWidget()
    qtbot.addWidget(widget)
    widget._test_mode.setChecked(True)

    assert saved[-1]["test_mode"] is True
    assert saved[-1]["test_address"] == "tester@example.com"


def test_test_mode_cannot_enable_without_valid_test_address(
        qtbot, monkeypatch):
    config = {"graph": {"test_address": "", "test_mode": False}}
    saved = []
    monkeypatch.setattr("app.ui.settings_tab.get_config", lambda: config)
    monkeypatch.setattr(
        "app.ui.settings_tab.save_config", lambda value: saved.append(value))
    monkeypatch.setattr(
        "app.ui.settings_tab.QMessageBox.warning", lambda *args: None)

    widget = _GraphSettingsWidget()
    qtbot.addWidget(widget)
    widget._test_mode.setChecked(True)

    assert widget._test_mode.isChecked() is False
    assert saved == []
