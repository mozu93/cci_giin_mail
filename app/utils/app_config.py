import json
from pathlib import Path


def _config_path() -> Path:
    return Path(__file__).parent.parent.parent / "app_config.json"


def _db_default_path() -> Path:
    return Path(__file__).parent.parent.parent / "cci_mail.db"


def get_config() -> dict:
    p = _config_path()
    if p.exists():
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_config(config: dict) -> None:
    p = _config_path()
    with open(p, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def get_db_path() -> str:
    config = get_config()
    db_path = config.get("db_path", "")
    if db_path:
        return db_path
    return str(_db_default_path())


def get_graph_config() -> dict:
    return get_config().get("graph", {})


def get_db_type() -> str:
    """'sqlite' または 'postgresql' を返す（デフォルトは 'sqlite'）"""
    return get_config().get("db_type", "sqlite")


def get_pg_config() -> dict:
    """PostgreSQL接続設定を返す"""
    defaults = {
        "host": "localhost",
        "port": "5432",
        "database": "cci_mail",
        "user": "",
        "password": "",
    }
    return {**defaults, **get_config().get("postgresql", {})}
