import json
from pathlib import Path

_PATH = Path(__file__).parent.parent.parent / "ui_settings.json"


def _load() -> dict:
    if _PATH.exists():
        try:
            return json.loads(_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save(data: dict):
    _PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def get_font_size(key: str, default: int) -> int:
    return _load().get("font_sizes", {}).get(key, default)


def set_font_size(key: str, size: int):
    data = _load()
    data.setdefault("font_sizes", {})[key] = size
    _save(data)


def get_hidden_columns(key: str) -> list[int]:
    return _load().get("hidden_columns", {}).get(key, [])


def set_hidden_columns(key: str, hidden_columns: list[int]):
    data = _load()
    data.setdefault("hidden_columns", {})[key] = hidden_columns
    _save(data)


def get_last_staff() -> str:
    return _load().get("last_staff", "")


def set_last_staff(name: str):
    data = _load()
    data["last_staff"] = name
    _save(data)
