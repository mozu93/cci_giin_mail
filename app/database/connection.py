from sqlalchemy import create_engine, event
from sqlalchemy.engine import URL as SaURL
from sqlalchemy.orm import sessionmaker, Session
from app.database.models import Base

_engine = None
_SessionLocal = None


def _configure_sqlite(dbapi_conn, connection_record):
    dbapi_conn.execute("PRAGMA journal_mode=WAL")
    dbapi_conn.execute("PRAGMA foreign_keys=ON")
    dbapi_conn.execute("PRAGMA busy_timeout=5000")


def _migrate_sqlite(engine):
    """既存SQLite DBにカラム追加が必要な場合だけ ALTER TABLE を実行する"""
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

        # reception_logs テーブルは create_all で自動生成されるため追加不要

        history_cols = {
            row[1] for row in conn.execute(text("PRAGMA table_info(member_history)"))
        }
        if "import_batch_id" not in history_cols:
            conn.execute(text(
                "ALTER TABLE member_history ADD COLUMN import_batch_id TEXT"
            ))
            conn.commit()

        members_cols = {
            row[1] for row in conn.execute(text("PRAGMA table_info(members)"))
        }
        if "photo_thumb" not in members_cols:
            conn.execute(text("ALTER TABLE members ADD COLUMN photo_thumb BLOB"))
            conn.commit()
        if "photo_full" not in members_cols:
            conn.execute(text("ALTER TABLE members ADD COLUMN photo_full BLOB"))
            conn.commit()


def _migrate_postgresql(engine):
    from sqlalchemy import inspect, text
    insp = inspect(engine)
    members_cols = {col["name"] for col in insp.get_columns("members")}
    with engine.begin() as conn:
        if "photo_thumb" not in members_cols:
            conn.execute(text("ALTER TABLE members ADD COLUMN photo_thumb BYTEA"))
        if "photo_full" not in members_cols:
            conn.execute(text("ALTER TABLE members ADD COLUMN photo_full BYTEA"))


def get_engine(db_path: str | None = None):
    global _engine
    if _engine is None:
        from app.utils.app_config import get_db_type, get_pg_config, get_db_path
        db_type = get_db_type()

        if db_type == "postgresql":
            pg = get_pg_config()
            url = SaURL.create(
                "postgresql+psycopg2",
                username=pg["user"],
                password=pg["password"],
                host=pg["host"],
                port=int(pg.get("port") or 5432),
                database=pg["database"],
            )
            _engine = create_engine(url, echo=False,
                                    pool_size=5, max_overflow=10,
                                    pool_pre_ping=True)
        else:
            if db_path is None:
                db_path = get_db_path()
            _engine = create_engine(f"sqlite:///{db_path}", echo=False)
            event.listen(_engine, "connect", _configure_sqlite)

        Base.metadata.create_all(_engine)

        if db_type == "sqlite":
            _migrate_sqlite(_engine)
        else:
            _migrate_postgresql(_engine)

    return _engine


def get_session() -> Session:
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=get_engine())
    return _SessionLocal()


def reset_engine() -> None:
    """テスト用・設定変更後：エンジンをリセットする"""
    global _engine, _SessionLocal
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _SessionLocal = None
