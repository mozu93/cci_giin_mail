from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from app.database.models import Base

_engine = None
_SessionLocal = None


def _configure_sqlite(dbapi_conn, connection_record):
    dbapi_conn.execute("PRAGMA journal_mode=WAL")
    dbapi_conn.execute("PRAGMA foreign_keys=ON")
    dbapi_conn.execute("PRAGMA busy_timeout=5000")  # 書き込み競合時に5秒リトライ


def _migrate(engine):
    """既存DBにカラム追加が必要な場合だけALTER TABLEを実行する"""
    from sqlalchemy import text
    with engine.connect() as conn:
        meetings_cols = {
            row[1] for row in conn.execute(text("PRAGMA table_info(meetings)"))
        }
        if "target_position_ids" not in meetings_cols:
            conn.execute(text(
                "ALTER TABLE meetings ADD COLUMN target_position_ids TEXT"
            ))
            conn.commit()

        members_cols = {
            row[1] for row in conn.execute(text("PRAGMA table_info(members)"))
        }
        if "display_order" not in members_cols:
            conn.execute(text(
                "ALTER TABLE members ADD COLUMN display_order INTEGER"
            ))
            conn.commit()

        attendance_cols = {
            row[1] for row in conn.execute(text("PRAGMA table_info(attendance_records)"))
        }
        if "actual_status" not in attendance_cols:
            conn.execute(text(
                "ALTER TABLE attendance_records ADD COLUMN actual_status TEXT DEFAULT ''"
            ))
            conn.commit()


def get_engine(db_path: str | None = None):
    global _engine
    if _engine is None:
        if db_path is None:
            from app.utils.app_config import get_db_path
            db_path = get_db_path()
        _engine = create_engine(f"sqlite:///{db_path}", echo=False)
        event.listen(_engine, "connect", _configure_sqlite)
        Base.metadata.create_all(_engine)
        _migrate(_engine)
    return _engine


def get_session() -> Session:
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=get_engine())
    return _SessionLocal()


def reset_engine() -> None:
    """テスト用：エンジンをリセットする"""
    global _engine, _SessionLocal
    _engine = None
    _SessionLocal = None
