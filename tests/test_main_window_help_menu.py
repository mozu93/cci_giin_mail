class _FakeSession:
    def close(self):
        pass


class _Staff:
    def __init__(self, id, name, is_admin):
        self.id = id
        self.name = name
        self.is_admin = is_admin


def _find_help_action(window, text):
    for action in window.menuBar().actions():
        menu = action.menu()
        if menu and action.text() == "ヘルプ":
            for sub in menu.actions():
                if sub.text() == text:
                    return sub
    return None


def test_user_manual_always_visible_for_admin(qtbot, monkeypatch):
    monkeypatch.setattr("app.ui.main_window.get_session", lambda: _FakeSession())
    monkeypatch.setattr("app.ui.main_window.get_staff_by_name",
                        lambda s, name: _Staff(1, "水谷", is_admin=True))

    from app.ui.main_window import MainWindow
    window = MainWindow(staff_name="水谷")
    qtbot.addWidget(window)

    assert _find_help_action(window, "使い方マニュアル") is not None


def test_admin_manual_present_for_admin(qtbot, monkeypatch):
    monkeypatch.setattr("app.ui.main_window.get_session", lambda: _FakeSession())
    monkeypatch.setattr("app.ui.main_window.get_staff_by_name",
                        lambda s, name: _Staff(1, "水谷", is_admin=True))

    from app.ui.main_window import MainWindow
    window = MainWindow(staff_name="水谷")
    qtbot.addWidget(window)

    assert _find_help_action(window, "管理者マニュアル") is not None


def test_admin_manual_absent_for_non_admin(qtbot, monkeypatch):
    monkeypatch.setattr("app.ui.main_window.get_session", lambda: _FakeSession())
    monkeypatch.setattr("app.ui.main_window.get_staff_by_name",
                        lambda s, name: _Staff(2, "山田", is_admin=False))

    from app.ui.main_window import MainWindow
    window = MainWindow(staff_name="山田")
    qtbot.addWidget(window)

    assert _find_help_action(window, "使い方マニュアル") is not None
    assert _find_help_action(window, "管理者マニュアル") is None


def test_admin_manual_absent_when_staff_not_found(qtbot, monkeypatch):
    monkeypatch.setattr("app.ui.main_window.get_session", lambda: _FakeSession())
    monkeypatch.setattr("app.ui.main_window.get_staff_by_name",
                        lambda s, name: None)

    from app.ui.main_window import MainWindow
    window = MainWindow(staff_name="不明")
    qtbot.addWidget(window)

    assert _find_help_action(window, "使い方マニュアル") is not None
    assert _find_help_action(window, "管理者マニュアル") is None
