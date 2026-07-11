import pytest
from pathlib import Path


def test_get_config_returns_empty_when_no_file(tmp_path, monkeypatch):
    monkeypatch.setattr("app.utils.app_config._config_path",
                        lambda: tmp_path / "app_config.json")
    from app.utils import app_config
    result = app_config.get_config()
    assert result == {}


def test_save_and_load_config(tmp_path, monkeypatch):
    from app.utils import app_config
    monkeypatch.setattr(app_config, "_config_path",
                        lambda: tmp_path / "app_config.json")

    app_config.save_config({"key": "value"})
    result = app_config.get_config()
    assert result["key"] == "value"


def test_get_graph_config(tmp_path, monkeypatch):
    from app.utils import app_config
    monkeypatch.setattr(app_config, "_config_path",
                        lambda: tmp_path / "app_config.json")

    app_config.save_config({
        "graph": {
            "tenant_id": "xxx-tenant",
            "client_id": "xxx-client",
            "client_secret": "xxx-secret",
            "from_address": "noreply@example.com",
        }
    })
    cfg = app_config.get_graph_config()
    assert cfg["tenant_id"] == "xxx-tenant"
    assert cfg["from_address"] == "noreply@example.com"


def test_is_first_run_true_when_no_config_file(tmp_path, monkeypatch):
    from app.utils import app_config
    monkeypatch.setattr(app_config, "_config_path",
                        lambda: tmp_path / "app_config.json")
    assert app_config.is_first_run() is True


def test_is_first_run_false_once_config_file_exists(tmp_path, monkeypatch):
    """既存インストール（本機能追加前に作られたconfig）を誤って初回設定扱いにしないこと。"""
    from app.utils import app_config
    monkeypatch.setattr(app_config, "_config_path",
                        lambda: tmp_path / "app_config.json")
    app_config.save_config({"graph": {"tenant_id": "xxx"}})
    assert app_config.is_first_run() is False
