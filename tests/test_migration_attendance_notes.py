import sqlite3
from sqlalchemy import create_engine, text
from app.database.connection import _migrate_sqlite
from app.database.models import Base


def test_migrate_sqlite_adds_notes_column(tmp_path):
    db_path = tmp_path / "old_schema.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "CREATE TABLE attendance_records (id INTEGER PRIMARY KEY, "
        "meeting_id INTEGER NOT NULL, member_id INTEGER NOT NULL, "
        "status TEXT NOT NULL, actual_status TEXT, "
        "proxy_title TEXT, proxy_name TEXT)")
    conn.commit()
    conn.close()

    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    _migrate_sqlite(engine)
    _migrate_sqlite(engine)  # 2回目もエラーにならないこと

    with engine.connect() as conn:
        cols = [row[1] for row in conn.execute(text("PRAGMA table_info(attendance_records)"))]
    assert cols.count("notes") == 1
    assert "notes" in cols
