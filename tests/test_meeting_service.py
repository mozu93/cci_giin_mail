import openpyxl
from app.database.models import ProcessedAttendanceMail
from app.services.meeting_service import (
    create_meeting, upsert_attendance, export_xlsx, delete_meeting, get_meetings,
    get_attendance_data, get_member_ids_by_status,
)
from app.services.member_service import create_member, delete_member
from app.services.position_service import create_position
from app.services.reception_log_service import create_log, get_logs
from datetime import date, datetime, timedelta

_FUTURE_DATE = date.today() + timedelta(days=30)


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
    meeting = create_meeting(db_session, "定例会議", _FUTURE_DATE)
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

    header_row = 9
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


def test_delete_meeting_with_reception_logs_does_not_raise(db_session):
    """受付ログ（ReceptionLog）が残っている会議を削除してもFK制約違反で
    クラッシュしないこと（reception_logs.meeting_idの孤立防止の回帰テスト）。"""
    position = create_position(db_session, "議員", 1)
    member = create_member(
        db_session, "A-201", "○○商事", "受付太郎", position_id=position.id)
    meeting = create_meeting(db_session, "定例会議", date(2026, 7, 20))
    upsert_attendance(db_session, meeting.id, member.id, "出席")
    create_log(db_session, meeting.id, member.id, "担当者A", "", "出席")

    delete_meeting(db_session, meeting.id)

    assert get_meetings(db_session) == []
    assert get_logs(db_session, meeting.id) == []


def test_delete_meeting_with_processed_attendance_mail_does_not_raise(db_session):
    """出欠メール取込み済みレコード（ProcessedAttendanceMail）が残っている
    会議を削除してもFK制約違反でクラッシュしないこと。"""
    meeting = create_meeting(db_session, "定例会議", date(2026, 7, 20))
    db_session.add(ProcessedAttendanceMail(
        message_id="msg-1", meeting_id=meeting.id, received_at=datetime.now()))
    db_session.commit()

    delete_meeting(db_session, meeting.id)

    assert get_meetings(db_session) == []
    assert db_session.query(ProcessedAttendanceMail).count() == 0


def test_get_attendance_data_excludes_members_who_joined_after_past_meeting(db_session):
    """開催済みの会議の名簿は固定される：会議日より後に入会した会員は
    一覧に含めない（新しい会員が過去の会議に出席したことにならないように）。"""
    position = create_position(db_session, "議員", 1)
    existing = create_member(
        db_session, "A-501", "既存商事", "既存太郎", position_id=position.id,
        created_at=datetime(2020, 1, 10))
    same_day = create_member(
        db_session, "A-502", "当日商事", "当日花子", position_id=position.id,
        created_at=datetime(2020, 1, 15, 23, 0))
    meeting = create_meeting(db_session, "過去の定例会議", date(2020, 1, 15))
    upsert_attendance(db_session, meeting.id, existing.id, "出席")

    # 会議翌日以降に入会した新規会員
    create_member(
        db_session, "A-503", "新規商事", "新人次郎", position_id=position.id,
        created_at=datetime(2020, 1, 16))

    names = [d["name"] for d in get_attendance_data(db_session, meeting.id)]
    assert "既存太郎" in names
    assert "当日花子" in names  # 会議当日入会は含める
    assert "新人次郎" not in names  # 会議翌日以降の入会は除外


def test_get_attendance_data_keeps_retired_members_with_past_records(db_session):
    """出欠記録が残っている会員は、会議後に退任していても過去の会議の
    出欠一覧から消えないこと（出席実績の保持）。"""
    position = create_position(db_session, "議員", 1)
    attendee = create_member(
        db_session, "A-511", "既存商事", "既存太郎", position_id=position.id,
        created_at=datetime(2020, 1, 1))
    unrelated = create_member(
        db_session, "A-512", "無関係商事", "無関係次郎", position_id=position.id,
        created_at=datetime(2020, 1, 1))
    meeting = create_meeting(db_session, "過去の定例会議", date(2020, 1, 15))
    upsert_attendance(db_session, meeting.id, attendee.id, "出席")

    delete_member(db_session, attendee.id, "担当者A")
    delete_member(db_session, unrelated.id, "担当者A")

    names = [d["name"] for d in get_attendance_data(db_session, meeting.id)]
    assert "既存太郎" in names  # 出欠記録が残っているため退任後も表示
    assert "無関係次郎" not in names  # 出欠記録が無い退任者は表示しない


def test_get_attendance_data_keeps_live_roster_for_upcoming_meeting(db_session):
    """未開催の会議は引き続き最新の名簿をライブ反映する（固定しない）。"""
    position = create_position(db_session, "議員", 1)
    meeting = create_meeting(db_session, "来月の定例会議", date(2099, 1, 15))

    create_member(
        db_session, "A-601", "新規商事", "新人次郎", position_id=position.id)

    names = [d["name"] for d in get_attendance_data(db_session, meeting.id)]
    assert "新人次郎" in names


def test_get_member_ids_by_status_excludes_members_who_joined_after_past_meeting(
        db_session):
    position = create_position(db_session, "議員", 1)
    existing = create_member(
        db_session, "A-701", "既存商事", "既存太郎", position_id=position.id,
        created_at=datetime(2020, 1, 10))
    meeting = create_meeting(db_session, "過去の定例会議", date(2020, 1, 15))
    upsert_attendance(db_session, meeting.id, existing.id, "出席")
    session_actual = db_session
    from app.services.meeting_service import update_actual_status
    update_actual_status(session_actual, meeting.id, existing.id, "出席")

    newcomer = create_member(
        db_session, "A-702", "新規商事", "新人次郎", position_id=position.id,
        created_at=datetime(2020, 1, 16))

    ids = get_member_ids_by_status(db_session, meeting.id, ["未回答"])
    assert newcomer.id not in ids


def test_export_xlsx_attendance_summary_counts(db_session, tmp_path):
    position = create_position(db_session, "議員", 1)
    kanji_position = create_position(db_session, "監事", 2)

    m1 = create_member(db_session, "A-101", "○○商事", "出席太郎",
                       position_id=position.id)
    m2 = create_member(db_session, "A-102", "△△産業", "代理次郎",
                       position_id=position.id)
    m3 = create_member(db_session, "A-103", "□□工業", "委任三郎",
                       position_id=position.id)
    m4 = create_member(db_session, "A-104", "××建設", "欠席四郎",
                       position_id=position.id)
    # 監事は議決権数から除外される
    m5 = create_member(db_session, "A-105", "◇◇興業", "監事五郎",
                       position_id=kanji_position.id)
    # 四日市商工会議所は議決権数から除外される
    m6 = create_member(db_session, "A-106", "四日市商工会議所", "議所六郎",
                       position_id=position.id)

    meeting = create_meeting(db_session, "定例会議", _FUTURE_DATE)
    upsert_attendance(db_session, meeting.id, m1.id, "出席")
    upsert_attendance(db_session, meeting.id, m2.id, "代理")
    upsert_attendance(db_session, meeting.id, m3.id, "委任")
    upsert_attendance(db_session, meeting.id, m4.id, "欠席")
    upsert_attendance(db_session, meeting.id, m5.id, "出席")
    upsert_attendance(db_session, meeting.id, m6.id, "出席")

    path = tmp_path / "attendance_summary.xlsx"
    export_xlsx(db_session, meeting.id, str(path))

    wb = openpyxl.load_workbook(path)
    ws = wb.active

    assert [ws.cell(row=5, column=c).value for c in range(1, 9)] == [
        "出席", "代理", "委任", "欠席", "議決権数",
        "実出席者数\n（出席+代理）", "事務局", "合計\n（飲み物用）",
    ]

    # 出席3（m1, m5監事, m6四日市）・代理1・委任1・欠席1
    assert ws.cell(row=6, column=1).value == 3
    assert ws.cell(row=6, column=2).value == 1
    assert ws.cell(row=6, column=3).value == 1
    assert ws.cell(row=6, column=4).value == 1
    # 議決権数 = 出席+代理+委任(5) - 監事(m5) - 四日市商工会議所(m6) = 3
    assert ws.cell(row=6, column=5).value == 3
    # 実出席者数 = 出席+代理（除外なし）= 4
    assert ws.cell(row=6, column=6).value == 4
    # 事務局は空欄で入力可能
    assert ws.cell(row=6, column=7).value is None
    # 合計（飲み物用）は実出席者数＋事務局の数式
    assert ws.cell(row=6, column=8).value == "=SUM(F6,G6)"


def test_export_xlsx_summary_note_mentions_exclusion_rule(db_session, tmp_path):
    meeting = create_meeting(db_session, "定例会議", date(2026, 7, 20))
    path = tmp_path / "attendance_note.xlsx"
    export_xlsx(db_session, meeting.id, str(path))

    wb = openpyxl.load_workbook(path)
    ws = wb.active
    note = ws.cell(row=7, column=1).value
    assert "監事" in note
    assert "四日市商工会議所" in note
