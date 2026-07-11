from PyQt6.QtWidgets import QMessageBox


class _FakeSession:
    def close(self):
        pass


class _Staff:
    def __init__(self, id, name, is_active=True, is_admin=False):
        self.id = id
        self.name = name
        self.is_active = is_active
        self.is_admin = is_admin


def test_staff_table_shows_admin_column(qtbot, monkeypatch):
    staff = [_Staff(1, "水谷", is_admin=True), _Staff(2, "山田", is_admin=False)]
    monkeypatch.setattr("app.ui.settings_tab.get_session", lambda: _FakeSession())
    monkeypatch.setattr("app.ui.settings_tab.get_all_staff", lambda s: staff)

    from app.ui.settings_tab import _StaffWidget
    w = _StaffWidget()
    qtbot.addWidget(w)

    assert w._table.item(0, 2).text() == "●"
    assert w._table.item(1, 2).text() == ""


def test_add_staff_with_admin_checkbox(qtbot, monkeypatch):
    monkeypatch.setattr("app.ui.settings_tab.get_session", lambda: _FakeSession())
    monkeypatch.setattr("app.ui.settings_tab.get_all_staff", lambda s: [])
    created = {}

    def fake_create_staff(session, name, is_admin=False):
        created["args"] = (name, is_admin)

    monkeypatch.setattr("app.ui.settings_tab.create_staff", fake_create_staff)

    from app.ui.settings_tab import _StaffWidget
    w = _StaffWidget()
    qtbot.addWidget(w)
    w._name.setText("新人")
    w._chk_admin.setChecked(True)
    w._add()

    assert created["args"] == ("新人", True)


def test_toggle_admin_warns_when_removing_last_admin(qtbot, monkeypatch):
    staff = [_Staff(1, "水谷", is_admin=True)]
    monkeypatch.setattr("app.ui.settings_tab.get_session", lambda: _FakeSession())
    monkeypatch.setattr("app.ui.settings_tab.get_all_staff", lambda s: staff)
    warned = []
    monkeypatch.setattr(
        QMessageBox, "question",
        staticmethod(lambda *a, **k: (warned.append(True),
                                       QMessageBox.StandardButton.No)[1]))
    toggled = []
    monkeypatch.setattr(
        "app.ui.settings_tab.set_admin",
        lambda session, sid, is_admin: toggled.append((sid, is_admin)))

    from app.ui.settings_tab import _StaffWidget
    w = _StaffWidget()
    qtbot.addWidget(w)
    w._table.setCurrentCell(0, 0)
    w._toggle_admin()

    assert warned, "最後の管理者を外そうとした際に警告が出ること"
    assert toggled == [], "Noを選んだ場合はset_adminが呼ばれないこと"


def test_toggle_admin_works_when_other_admin_exists(qtbot, monkeypatch):
    staff = [_Staff(1, "水谷", is_admin=True), _Staff(2, "山田", is_admin=True)]
    monkeypatch.setattr("app.ui.settings_tab.get_session", lambda: _FakeSession())
    monkeypatch.setattr("app.ui.settings_tab.get_all_staff", lambda s: staff)
    toggled = []
    monkeypatch.setattr(
        "app.ui.settings_tab.set_admin",
        lambda session, sid, is_admin: toggled.append((sid, is_admin)))

    from app.ui.settings_tab import _StaffWidget
    w = _StaffWidget()
    qtbot.addWidget(w)
    w._table.setCurrentCell(0, 0)
    w._toggle_admin()

    assert toggled == [(1, False)], "他に管理者がいれば確認なしで切り替わること"
