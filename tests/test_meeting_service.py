import openpyxl
from app.services.meeting_service import create_meeting, upsert_attendance, export_xlsx
from app.services.member_service import create_member
from app.services.position_service import create_position
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


def test_export_xlsx_writes_a4_portrait_page_setup(db_session, tmp_path):
    position = create_position(db_session, "議員", 1)
    member = create_member(
        db_session, "A-003", "□□工業", "佐藤次郎",
        title="代表取締役", position_id=position.id)
    meeting = create_meeting(db_session, "定例会議", date(2026, 7, 20))
    upsert_attendance(db_session, meeting.id, member.id, "出席")

    path = tmp_path / "attendance.xlsx"
    export_xlsx(db_session, meeting.id, str(path))

    wb = openpyxl.load_workbook(path)
    ws = wb.active
    assert str(ws.page_setup.paperSize) == str(ws.PAPERSIZE_A4)
    assert ws.page_setup.orientation == "portrait"
    assert ws.page_setup.fitToWidth == 1
    assert ws.page_setup.fitToHeight == 0
    assert ws.sheet_properties.pageSetUpPr.fitToPage is True

    header_row = 4
    assert [ws.cell(row=header_row, column=c).value for c in range(1, 8)] == [
        "No.", "役職", "事業所名", "所属役職", "氏名", "事前", "代理",
    ]
    for c in range(1, 8):
        assert ws.cell(row=header_row, column=c).font.size == 11

    data_row = header_row + 1
    assert ws.cell(row=data_row, column=1).value == 1
    assert ws.cell(row=data_row, column=2).value == "議員"
    assert ws.cell(row=data_row, column=3).value == "□□工業"
    assert ws.cell(row=data_row, column=4).value == "代表取締役"
    assert ws.cell(row=data_row, column=5).value == "佐藤次郎"
    assert ws.cell(row=data_row, column=6).value == "出席"
    assert ws.cell(row=data_row, column=1).font.size == 11
    assert ws.cell(row=data_row, column=1).alignment.shrink_to_fit is True
    assert ws.cell(row=data_row, column=1).alignment.horizontal == "center"
    assert ws.cell(row=data_row, column=5).alignment.horizontal == "center"
    assert ws.cell(row=data_row, column=3).alignment.horizontal != "center"

    # 列幅は指定ピクセル値 [30, 45, 235, 129, 93, 45, 141] を
    # (px - 5) / 7 でExcelの文字単位に換算した値と一致すること
    expected_px = [30, 45, 235, 129, 93, 45, 141]
    for c in range(1, 8):
        w = ws.column_dimensions[ws.cell(row=header_row, column=c).column_letter].width
        assert w == round((expected_px[c - 1] - 5) / 7, 2)
