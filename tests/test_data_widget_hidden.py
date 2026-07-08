import os


def test_data_tab_hidden_by_default(qtbot, monkeypatch):
    monkeypatch.delenv("CCI_MAIL_DEV_TOOLS", raising=False)
    from app.ui.settings_tab import SettingsTab
    tab = SettingsTab()
    qtbot.addWidget(tab)
    inner = tab.findChild(__import__("PyQt6.QtWidgets", fromlist=["QTabWidget"]).QTabWidget)
    labels = [inner.tabText(i) for i in range(inner.count())]
    assert "データ管理" not in labels


def test_data_tab_visible_with_env_flag(qtbot, monkeypatch):
    monkeypatch.setenv("CCI_MAIL_DEV_TOOLS", "1")
    from app.ui.settings_tab import SettingsTab
    tab = SettingsTab()
    qtbot.addWidget(tab)
    inner = tab.findChild(__import__("PyQt6.QtWidgets", fromlist=["QTabWidget"]).QTabWidget)
    labels = [inner.tabText(i) for i in range(inner.count())]
    assert "データ管理" in labels
