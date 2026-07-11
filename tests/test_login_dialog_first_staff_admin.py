class _FakeSession:
    def close(self):
        pass


def test_first_staff_added_from_login_becomes_admin(qtbot, monkeypatch):
    monkeypatch.setattr(
        "app.ui.dialogs.login_dialog.get_session", lambda: _FakeSession())
    monkeypatch.setattr(
        "app.ui.dialogs.login_dialog.get_all_staff", lambda s: [])
    monkeypatch.setattr(
        "app.ui.dialogs.login_dialog.get_last_staff", lambda: "")

    created = {}

    def fake_create_staff(session, name, is_admin=False):
        created["args"] = (name, is_admin)

    monkeypatch.setattr(
        "app.ui.dialogs.login_dialog.create_staff", fake_create_staff)

    from PyQt6.QtWidgets import QInputDialog, QMessageBox
    monkeypatch.setattr(QInputDialog, "getText",
                        staticmethod(lambda *a, **k: ("新人担当者", True)))
    monkeypatch.setattr(QMessageBox, "information",
                        staticmethod(lambda *a, **k: None))

    from app.ui.dialogs.login_dialog import LoginDialog
    dlg = LoginDialog()
    qtbot.addWidget(dlg)

    dlg._add_staff()

    assert created["args"] == ("新人担当者", True)
