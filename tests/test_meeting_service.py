from app.services.meeting_service import create_meeting, upsert_attendance
from app.services.member_service import create_member
from datetime import date


def test_upsert_attendance_saves_notes(db_session):
    member = create_member(db_session, "A-001", "○○商事", "山田太郎")
    meeting = create_meeting(db_session, "常議員会", date(2026, 7, 20))

    record = upsert_attendance(
        db_session, meeting.id, member.id, "出席", notes="体調不良のため途中退席予定")

    assert record.notes == "体調不良のため途中退席予定"


def test_upsert_attendance_notes_defaults_to_empty(db_session):
    member = create_member(db_session, "A-002", "△△産業", "鈴木花子")
    meeting = create_meeting(db_session, "常議員会", date(2026, 7, 20))

    record = upsert_attendance(db_session, meeting.id, member.id, "欠席")

    assert record.notes == ""
