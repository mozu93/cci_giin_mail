# tests/test_migration_parity.py
"""SQLiteとPostgreSQLのマイグレーション内容が食い違わないことを検証する。

列を追加したときに SQLite 側だけ書いて PostgreSQL 側を書き忘れると、
ネットワーク運用（PostgreSQL）の既存DBだけ列が増えず起動時に失敗する。
実際のPostgreSQLサーバーが無くても検出できるよう、マイグレーション関数の
ソースから ALTER TABLE ... ADD COLUMN を抽出して突き合わせる。
"""
import inspect
import re

from app.database import connection

# PostgreSQL対応（2026-06-24）より前に追加された列。
# PostgreSQLのDBはその時点のモデルから create_all で作られるため、
# これらは最初から存在し、PostgreSQL側のマイグレーションは不要。
_PRE_POSTGRESQL_COLUMNS = {
    ("attendance_records", "actual_status"),
    ("meetings", "target_position_ids"),
    ("member_history", "import_batch_id"),
    ("members", "display_order"),
}

_ADD_COLUMN = re.compile(r"ALTER TABLE\s+(\w+)\s+ADD COLUMN\s+(\w+)", re.IGNORECASE)


def _added_columns(func) -> set[tuple[str, str]]:
    source = inspect.getsource(func)
    # 複数行に分割された文字列リテラルの連結を1行に戻してから抽出する
    joined = re.sub(r'"\s*\n\s*"', "", source)
    return set(_ADD_COLUMN.findall(re.sub(r"\s+", " ", joined)))


def test_sqlite_migrations_are_mirrored_in_postgresql():
    sqlite_cols = _added_columns(connection._migrate_sqlite)
    postgresql_cols = _added_columns(connection._migrate_postgresql)

    missing = sqlite_cols - postgresql_cols - _PRE_POSTGRESQL_COLUMNS
    assert not missing, (
        "PostgreSQL側のマイグレーションが未実装の列があります: "
        + ", ".join(f"{table}.{column}" for table, column in sorted(missing))
    )


def test_committee_and_recent_columns_are_migrated_on_both_backends():
    """今回追加した列が両方のバックエンドで移行されること。"""
    expected = {
        ("meetings", "target_committee_ids"),
        ("members", "committee_role"),
        ("member_history", "exclude_from_recent"),
    }
    assert expected <= _added_columns(connection._migrate_sqlite)
    assert expected <= _added_columns(connection._migrate_postgresql)
