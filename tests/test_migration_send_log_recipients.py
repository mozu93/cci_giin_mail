import sqlite3
from sqlalchemy import create_engine, text

from app.database.connection import _migrate_sqlite
from app.database.models import Base


def test_migrate_sqlite_adds_send_log_recipient_columns(tmp_path):
    db_path = tmp_path / "old_schema.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "CREATE TABLE send_logs ("
        "id INTEGER PRIMARY KEY, job_id INTEGER NOT NULL, member_id INTEGER, "
        "to_address TEXT NOT NULL, subject TEXT NOT NULL, status TEXT NOT NULL, "
        "error_message TEXT, sent_at DATETIME)"
    )
    conn.commit()
    conn.close()

    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    _migrate_sqlite(engine)
    _migrate_sqlite(engine)

    with engine.connect() as conn:
        columns = {
            row[1] for row in conn.execute(text("PRAGMA table_info(send_logs)"))
        }
    assert "cc_addresses" in columns
    assert "bcc_addresses" in columns
