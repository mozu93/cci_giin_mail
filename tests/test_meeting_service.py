import openpyxl
from app.services.meeting_service import create_meeting, upsert_attendance, export_xlsx
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


def test_export_xlsx_writes_a4_page_setup(db_session, tmp_path):
    member = create_member(db_session, "A-003", "□□工業", "佐藤次郎")
    meeting = create_meeting(db_session, "定例会議", date(2026, 7, 20))
    upsert_attendance(db_session, meeting.id, member.id, "出席")

    path = tmp_path / "attendance.xlsx"
    export_xlsx(db_session, meeting.id, str(path))

    wb = openpyxl.load_workbook(path)
    ws = wb.active
    assert str(ws.page_setup.paperSize) == str(ws.PAPERSIZE_A4)
    assert ws.page_setup.fitToWidth == 1
    assert ws.page_setup.fitToHeight == 0
    assert ws.sheet_properties.pageSetUpPr.fitToPage is True
    assert ws["A4"].value == "会員番号"
    assert ws.cell(row=5, column=2).value == "□□工業"
