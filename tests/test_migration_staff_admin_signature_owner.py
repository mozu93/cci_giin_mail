import sqlite3
from sqlalchemy import create_engine, text
from app.database.connection import _migrate_sqlite
from app.database.models import Base


def test_migrate_sqlite_adds_is_admin_and_staff_id_columns(tmp_path):
    db_path = tmp_path / "old_schema.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "CREATE TABLE staff (id INTEGER PRIMARY KEY, name TEXT NOT NULL, "
        "is_active BOOLEAN)")
    conn.execute(
        "CREATE TABLE signatures (id INTEGER PRIMARY KEY, name TEXT NOT NULL, "
        "body TEXT NOT NULL, is_default BOOLEAN)")
    conn.commit()
    conn.close()

    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    _migrate_sqlite(engine)

    with engine.connect() as conn:
        staff_cols = {row[1] for row in conn.execute(text("PRAGMA table_info(staff)"))}
        sig_cols = {row[1] for row in conn.execute(text("PRAGMA table_info(signatures)"))}
    assert "is_admin" in staff_cols
    assert "staff_id" in sig_cols


def test_migrate_sqlite_is_idempotent(tmp_path):
    db_path = tmp_path / "old_schema2.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "CREATE TABLE staff (id INTEGER PRIMARY KEY, name TEXT NOT NULL, "
        "is_active BOOLEAN)")
    conn.execute(
        "CREATE TABLE signatures (id INTEGER PRIMARY KEY, name TEXT NOT NULL, "
        "body TEXT NOT NULL, is_default BOOLEAN)")
    conn.commit()
    conn.close()

    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    _migrate_sqlite(engine)
    _migrate_sqlite(engine)  # 2回目もエラーにならないこと

    with engine.connect() as conn:
        staff_cols = [row[1] for row in conn.execute(text("PRAGMA table_info(staff)"))]
        sig_cols = [row[1] for row in conn.execute(text("PRAGMA table_info(signatures)"))]
    assert staff_cols.count("is_admin") == 1
    assert sig_cols.count("staff_id") == 1
    assert "is_admin" in staff_cols
    assert "staff_id" in sig_cols
