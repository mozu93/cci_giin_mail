import pytest
import openpyxl
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from app.database.models import Base


def _enable_fk(dbapi_conn, connection_record):
    dbapi_conn.execute("PRAGMA foreign_keys=ON")


@pytest.fixture
def db_sessionmaker():
    """複数セッションを都度生成できるファクトリ。session.close()後の
    デタッチ挙動を再現するテスト(例: DetachedInstanceErrorの回帰テスト)で使う。"""
    engine = create_engine("sqlite:///:memory:")
    event.listen(engine, "connect", _enable_fk)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    yield Session
    Base.metadata.drop_all(engine)


@pytest.fixture
def db_session(db_sessionmaker):
    session = db_sessionmaker()
    yield session
    session.close()


@pytest.fixture
def sample_excel(tmp_path):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["会員番号", "事業所名", "事業所名フリガナ", "役職名", "氏名", "氏名フリガナ",
                "会議所役職", "メール1", "ラベル1", "メール2", "ラベル2"])
    ws.append(["A-001", "○○商事", "マルマルショウジ", "代表取締役", "山田 太郎",
                "ヤマダ タロウ", "議員", "yamada@example.com", "本人", "", ""])
    ws.append(["A-002", "△△産業", "サンカクサンギョウ", "社長", "鈴木 花子",
                "スズキ ハナコ", "議員", "suzuki@example.com", "本人",
                "somu@example.com", "総務"])
    path = tmp_path / "members.xlsx"
    wb.save(path)
    return str(path)
