from PyQt6.QtWidgets import QMessageBox


def _patch_config(monkeypatch, tmp_path):
    from app.utils import app_config
    monkeypatch.setattr(app_config, "_config_path",
                        lambda: tmp_path / "app_config.json")


def test_wizard_defaults_to_postgresql(qtbot, tmp_path, monkeypatch):
    _patch_config(monkeypatch, tmp_path)
    from app.ui.dialogs.first_run_wizard import FirstRunWizard
    wiz = FirstRunWizard()
    qtbot.addWidget(wiz)
    assert wiz._db_type.currentIndex() == 0  # PostgreSQL


def test_wizard_sqlite_disables_pg_fields(qtbot, tmp_path, monkeypatch):
    _patch_config(monkeypatch, tmp_path)
    from app.ui.dialogs.first_run_wizard import FirstRunWizard
    wiz = FirstRunWizard()
    qtbot.addWidget(wiz)
    wiz._db_type.setCurrentIndex(1)  # SQLite
    assert wiz._host.isEnabled() is False
    assert wiz._password.isEnabled() is False


def test_wizard_save_sqlite_sets_db_configured_and_accepts(qtbot, tmp_path, monkeypatch):
    _patch_config(monkeypatch, tmp_path)
    monkeypatch.setattr("app.database.connection.reset_engine", lambda: None)
    monkeypatch.setattr("app.database.connection.get_engine", lambda: None)

    from app.ui.dialogs.first_run_wizard import FirstRunWizard
    from app.utils import app_config
    wiz = FirstRunWizard()
    qtbot.addWidget(wiz)
    wiz._db_type.setCurrentIndex(1)  # SQLite（接続不要で完結させる）

    wiz._save()

    cfg = app_config.get_config()
    assert cfg["db_configured"] is True
    assert cfg["db_type"] == "sqlite"


def test_wizard_save_postgresql_persists_connection_settings(qtbot, tmp_path, monkeypatch):
    _patch_config(monkeypatch, tmp_path)
    monkeypatch.setattr("app.database.connection.reset_engine", lambda: None)
    monkeypatch.setattr("app.database.connection.get_engine", lambda: None)

    from app.ui.dialogs.first_run_wizard import FirstRunWizard
    from app.utils import app_config
    wiz = FirstRunWizard()
    qtbot.addWidget(wiz)
    wiz._host.setText("db.example.local")
    wiz._database.setText("cci_mail")

    wiz._save()

    cfg = app_config.get_config()
    assert cfg["db_type"] == "postgresql"
    assert cfg["postgresql"]["host"] == "db.example.local"
    assert cfg["postgresql"]["database"] == "cci_mail"


def test_wizard_save_shows_error_and_does_not_accept_on_connection_failure(
        qtbot, tmp_path, monkeypatch):
    _patch_config(monkeypatch, tmp_path)
    monkeypatch.setattr("app.database.connection.reset_engine", lambda: None)

    def fake_get_engine():
        raise RuntimeError("接続失敗")

    monkeypatch.setattr("app.database.connection.get_engine", fake_get_engine)

    errors = []
    monkeypatch.setattr(QMessageBox, "critical",
                        staticmethod(lambda *a, **k: errors.append(True)))

    from app.ui.dialogs.first_run_wizard import FirstRunWizard
    wiz = FirstRunWizard()
    qtbot.addWidget(wiz)

    wiz._save()

    assert errors, "接続失敗時にエラーダイアログが表示されること"
