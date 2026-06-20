import json
import pytest
from pathlib import Path


@pytest.fixture
def tmp_config(tmp_path, monkeypatch):
    config_file = tmp_path / "app_config.json"
    monkeypatch.setattr("app.utils.app_config._CONFIG_DIR",
                        lambda: tmp_path)
    return config_file


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
