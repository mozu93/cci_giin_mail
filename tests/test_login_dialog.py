def test_login_button_disabled_until_staff_selected(qtbot, monkeypatch, tmp_path):
    monkeypatch.setattr(
        "app.services.settings_service._PATH", tmp_path / "ui_settings.json")

    class _Staff:
        def __init__(self, name):
            self.name = name
            self.is_active = True

    monkeypatch.setattr(
        "app.ui.dialogs.login_dialog.get_session", lambda: _FakeSession())
    monkeypatch.setattr(
        "app.ui.dialogs.login_dialog.get_all_staff",
        lambda s: [_Staff("担当者A"), _Staff("担当者B")])

    from app.ui.dialogs.login_dialog import LoginDialog
    dlg = LoginDialog()
    qtbot.addWidget(dlg)

    assert dlg._btn_login.isEnabled() is False
    dlg._combo.setCurrentIndex(1)
    assert dlg._btn_login.isEnabled() is True


def test_last_staff_is_remembered(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.services.settings_service._PATH", tmp_path / "ui_settings.json")
    from app.services.settings_service import get_last_staff, set_last_staff
    assert get_last_staff() == ""
    set_last_staff("担当者A")
    assert get_last_staff() == "担当者A"


class _FakeSession:
    def close(self):
        pass
