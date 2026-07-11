import json
import os
import sys
from pathlib import Path


def _app_data_dir() -> Path:
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or Path.home()
    else:
        base = Path.home()
    d = Path(base) / "cci-mail"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _config_path() -> Path:
    new_path = _app_data_dir() / "app_config.json"
    old_path = Path(__file__).parent.parent.parent / "app_config.json"
    if not new_path.exists() and old_path.exists():
        import shutil
        shutil.copy2(old_path, new_path)
    return new_path


def _db_default_path() -> Path:
    old_path = Path(__file__).parent.parent.parent / "cci_mail.db"
    if old_path.exists():
        return old_path
    return _app_data_dir() / "cci_mail.db"


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


def get_html_export_path() -> str:
    """HTML出力先ファイルパス（未設定時は空文字）"""
    return get_config().get("html_export_path", "")


def is_first_run() -> bool:
    """設定ファイルが一度も保存されていない（＝DB接続先が未設定の）状態かどうか。

    既存インストール（本機能追加前に作られたconfig）は、キーの有無に関わらず
    ファイルが存在する時点で「設定済み」とみなし、初回設定ウィザードを出さない。
    """
    return not _config_path().exists()


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
