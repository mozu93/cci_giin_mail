from app.utils import app_config


def test_save_and_get_attendance_mail_folder(monkeypatch, tmp_path):
    monkeypatch.setattr(app_config, "_config_path", lambda: tmp_path / "app_config.json")

    assert app_config.get_attendance_mail_folder() == ""
    app_config.save_attendance_mail_folder("常議員会出欠")
    assert app_config.get_attendance_mail_folder() == "常議員会出欠"


def test_save_and_get_attendance_mail_subject_filter(monkeypatch, tmp_path):
    monkeypatch.setattr(app_config, "_config_path", lambda: tmp_path / "app_config.json")

    assert app_config.get_attendance_mail_subject_filter() == ""
    app_config.save_attendance_mail_subject_filter("出欠連絡")
    assert app_config.get_attendance_mail_subject_filter() == "出欠連絡"
