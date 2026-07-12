import os

from PyQt6.QtWidgets import QTabWidget


class _FakeSession:
    def close(self):
        pass


class _Staff:
    def __init__(self, id, name, is_admin):
        self.id = id
        self.name = name
        self.is_admin = is_admin


def _patch_common(monkeypatch, staff_lookup=None):
    monkeypatch.setattr("app.ui.settings_tab.get_session", lambda: _FakeSession())
    monkeypatch.setattr("app.ui.settings_tab.get_staff_by_name",
                        lambda s, name: staff_lookup)
    monkeypatch.setattr("app.ui.settings_tab.get_signatures", lambda s, sid: [])
    monkeypatch.setattr("app.ui.settings_tab.get_all_staff", lambda s: [])
    monkeypatch.setattr("app.ui.settings_tab.get_committees", lambda s: [])
    monkeypatch.setattr("app.ui.settings_tab.get_positions", lambda s: [])


def test_data_tab_hidden_by_default(qtbot, monkeypatch):
    monkeypatch.delenv("CCI_MAIL_DEV_TOOLS", raising=False)
    from app.ui.settings_tab import SettingsTab
    tab = SettingsTab()
    qtbot.addWidget(tab)
    inner = tab.findChild(QTabWidget)
    labels = [inner.tabText(i) for i in range(inner.count())]
    assert "データ管理" not in labels


def test_data_tab_visible_with_env_flag(qtbot, monkeypatch):
    monkeypatch.setenv("CCI_MAIL_DEV_TOOLS", "1")
    from app.ui.settings_tab import SettingsTab
    tab = SettingsTab()
    qtbot.addWidget(tab)
    inner = tab.findChild(QTabWidget)
    labels = [inner.tabText(i) for i in range(inner.count())]
    assert "データ管理" in labels


def test_data_tab_visible_for_admin_without_env_flag(qtbot, monkeypatch):
    monkeypatch.delenv("CCI_MAIL_DEV_TOOLS", raising=False)
    _patch_common(monkeypatch, staff_lookup=_Staff(1, "水谷", is_admin=True))
    from app.ui.settings_tab import SettingsTab
    tab = SettingsTab(staff_name="水谷")
    qtbot.addWidget(tab)
    inner = tab.findChild(QTabWidget)
    labels = [inner.tabText(i) for i in range(inner.count())]
    assert "データ管理" in labels


def test_data_tab_hidden_for_non_admin_without_env_flag(qtbot, monkeypatch):
    monkeypatch.delenv("CCI_MAIL_DEV_TOOLS", raising=False)
    _patch_common(monkeypatch, staff_lookup=_Staff(1, "山田", is_admin=False))
    from app.ui.settings_tab import SettingsTab
    tab = SettingsTab(staff_name="山田")
    qtbot.addWidget(tab)
    inner = tab.findChild(QTabWidget)
    labels = [inner.tabText(i) for i in range(inner.count())]
    assert "データ管理" not in labels
