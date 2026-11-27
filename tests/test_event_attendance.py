import sqlite3
from datetime import date, timedelta

from sqlalchemy import create_engine, text

from app.database.connection import _migrate_sqlite
from app.database.models import Base
from app.services.meeting_service import (
    KIND_EVENT, KIND_MEETING, create_meeting, get_attendance_data,
    get_member_ids_by_status, get_reception_summary, is_event,
    set_event_attendance,
)
from app.services.member_service import create_member

_FUTURE = date.today() + timedelta(days=30)


def test_create_meeting_defaults_to_meeting_kind(db_session):
    m = create_meeting(db_session, "総会", _FUTURE)
    assert m.kind == KIND_MEETING
    assert not is_event(db_session, m.id)


def test_create_event_kind(db_session):
    m = create_meeting(db_session, "懇親会", _FUTURE, kind=KIND_EVENT)
    assert is_event(db_session, m.id)


def test_create_meeting_rejects_unknown_kind(db_session):
    try:
        create_meeting(db_session, "x", _FUTURE, kind="その他")
    except ValueError:
        return
    raise AssertionError("ValueError が発生しなかった")


def test_set_event_attendance_check_and_uncheck(db_session):
    member = create_member(db_session, "A-001", "○○商事", "山田太郎")
    ev = create_meeting(db_session, "懇親会", _FUTURE, kind=KIND_EVENT)

    set_event_attendance(db_session, ev.id, member.id, True)
    d = get_attendance_data(db_session, ev.id)[0]
    assert d["status"] == "出席" and d["actual_status"] == "出席"

    set_event_attendance(db_session, ev.id, member.id, False)
    d = get_attendance_data(db_session, ev.id)[0]
    assert d["status"] == "未回答" and d["actual_status"] == ""


def test_event_summary_counts_checked_only(db_session):
    a = create_member(db_session, "A-001", "○○商事", "山田太郎")
    create_member(db_session, "A-002", "△△産業", "鈴木花子")
    ev = create_meeting(db_session, "懇親会", _FUTURE, kind=KIND_EVENT)
    set_event_attendance(db_session, ev.id, a.id, True)

    s = get_reception_summary(db_session, ev.id)
    assert s["出席"] == 1 and s["合計"] == 1 and s["未受付"] == 1
    assert s["議決権数"] == 0


def test_event_member_ids_by_status(db_session):
    a = create_member(db_session, "A-001", "○○商事", "山田太郎")
    b = create_member(db_session, "A-002", "△△産業", "鈴木花子")
    ev = create_meeting(db_session, "懇親会", _FUTURE, kind=KIND_EVENT)
    set_event_attendance(db_session, ev.id, a.id, True)

    assert get_member_ids_by_status(db_session, ev.id, ["出席"]) == {a.id}
    assert get_member_ids_by_status(db_session, ev.id, ["未回答"]) == {b.id}
    assert get_member_ids_by_status(
        db_session, ev.id, ["出席", "未回答"]) == {a.id, b.id}


def test_migrate_sqlite_adds_kind_column(tmp_path):
    db_path = tmp_path / "old.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "CREATE TABLE meetings (id INTEGER PRIMARY KEY, name TEXT NOT NULL, "
        "date DATE NOT NULL, target_position_ids TEXT, target_committee_ids TEXT, "
        "created_at DATETIME)")
    conn.execute("INSERT INTO meetings (name, date) VALUES ('旧会議', '2026-01-01')")
    conn.commit()
    conn.close()

    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    _migrate_sqlite(engine)
    _migrate_sqlite(engine)

    with engine.connect() as c:
        cols = [r[1] for r in c.execute(text("PRAGMA table_info(meetings)"))]
        kind = c.execute(text("SELECT kind FROM meetings")).scalar()
    assert cols.count("kind") == 1
    assert kind == "会議"
