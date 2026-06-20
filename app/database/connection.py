from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from app.database.models import Base

_engine = None
_SessionLocal = None


def _configure_sqlite(dbapi_conn, connection_record):
    dbapi_conn.execute("PRAGMA journal_mode=WAL")
    dbapi_conn.execute("PRAGMA foreign_keys=ON")


def get_engine(db_path: str | None = None):
    global _engine
    if _engine is None:
        if db_path is None:
            from app.utils.app_config import get_db_path
            db_path = get_db_path()
        _engine = create_engine(f"sqlite:///{db_path}", echo=False)
        event.listen(_engine, "connect", _configure_sqlite)
        Base.metadata.create_all(_engine)
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
