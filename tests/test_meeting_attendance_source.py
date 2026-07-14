from datetime import date, timedelta
from app.database.models import Member
from app.services.meeting_service import (
    create_meeting, upsert_attendance, update_actual_status,
    get_member_ids_by_status, is_meeting_past,
)


def _add_member(session, member_number, name="テスト太郎"):
    m = Member(member_number=member_number, organization_name="テスト会社", name=name)
    session.add(m)
    session.commit()
    return m


def test_future_meeting_uses_pre_entry_status(db_session):
    m1 = _add_member(db_session, "A-001")
    m2 = _add_member(db_session, "A-002")
    meeting = create_meeting(db_session, "定例会", date.today() + timedelta(days=7))

    upsert_attendance(db_session, meeting.id, m1.id, "出席")
    # m2は当日受付だけ入力済み（本来は起こらないが、事前ステータスが優先されることを確認）
    update_actual_status(db_session, meeting.id, m2.id, "出席")

    assert not is_meeting_past(meeting)
    result = get_member_ids_by_status(db_session, meeting.id, ["出席"])
    assert result == {m1.id}


def test_past_meeting_uses_actual_status(db_session):
    m1 = _add_member(db_session, "A-001")
    m2 = _add_member(db_session, "A-002")
    meeting = create_meeting(db_session, "定例会", date.today() - timedelta(days=1))

    upsert_attendance(db_session, meeting.id, m1.id, "出席")  # 事前は出席だが当日は未受付
    update_actual_status(db_session, meeting.id, m2.id, "出席")

    assert is_meeting_past(meeting)
    result = get_member_ids_by_status(db_session, meeting.id, ["出席"])
    assert result == {m2.id}

    unreceived = get_member_ids_by_status(db_session, meeting.id, ["未回答"])
    assert unreceived == {m1.id}
