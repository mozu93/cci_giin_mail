import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from app.database.models import Base


def _enable_fk(dbapi_conn, connection_record):
    dbapi_conn.execute("PRAGMA foreign_keys=ON")


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    event.listen(engine, "connect", _enable_fk)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    Base.metadata.drop_all(engine)
