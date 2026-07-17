from app.services.attendance_mail_service import parse_body, normalize_org_name, STATUS_MAP

_SAMPLE_BODY = """
【出　　欠】出席(※代理)

【事業所名】　スーパーサンシ株式会社

【氏　　名】代表取締役　高倉　護

【代理者名】別所　喜三生

【代理役職】監査役

【受任者名（委任代理人）】

【備考】
"""

_SAMPLE_BODY_ATTEND = """
【出　　欠】出席

【事業所名】三重相互（株）

【氏　　名】議員　三重太郎

【代理者名】

【代理役職】

【受任者名（委任代理人）】

【備考】来月から担当者が変わります
"""


def test_parse_body_extracts_proxy_fields():
    fields = parse_body(_SAMPLE_BODY)
    assert fields["status_raw"] == "出席(※代理)"
    assert fields["org_name"] == "スーパーサンシ株式会社"
    assert fields["name"] == "代表取締役　高倉　護"
    assert fields["proxy_title"] == "監査役"
    assert fields["proxy_name"] == "別所　喜三生"
    assert fields["notes"] == ""


def test_parse_body_extracts_notes():
    fields = parse_body(_SAMPLE_BODY_ATTEND)
    assert fields["status_raw"] == "出席"
    assert fields["org_name"] == "三重相互（株）"
    assert fields["proxy_title"] == ""
    assert fields["proxy_name"] == ""
    assert fields["notes"] == "来月から担当者が変わります"


def test_status_map_covers_four_patterns():
    assert STATUS_MAP["出席"] == "出席"
    assert STATUS_MAP["出席(※代理)"] == "代理"
    assert STATUS_MAP["委任"] == "委任"
    assert STATUS_MAP["欠席"] == "欠席"


def test_normalize_org_name_strips_company_suffixes_and_spaces():
    assert normalize_org_name("スーパーサンシ株式会社") == normalize_org_name("スーパーサンシ")
    assert normalize_org_name("三重相互（株）") == normalize_org_name("三重相互(株)")
    assert normalize_org_name("三重 相互") == normalize_org_name("三重相互")


from app.services.attendance_mail_service import match_member
from app.services.member_service import create_member


def test_match_member_unique_match(db_session):
    create_member(db_session, "A-001", "○○商事", "山田太郎")
    m = match_member(db_session, "○○商事")
    assert m is not None
    assert m.member_number == "A-001"


def test_match_member_normalizes_company_suffix(db_session):
    create_member(db_session, "A-001", "スーパーサンシ株式会社", "高倉護")
    m = match_member(db_session, "スーパーサンシ（株）")
    assert m is not None
    assert m.member_number == "A-001"


def test_match_member_returns_none_when_no_match(db_session):
    create_member(db_session, "A-001", "○○商事", "山田太郎")
    assert match_member(db_session, "存在しない会社") is None


def test_match_member_returns_none_when_ambiguous(db_session):
    create_member(db_session, "A-001", "山田商事", "山田太郎")
    create_member(db_session, "A-002", "山田商事", "山田次郎")
    assert match_member(db_session, "山田商事") is None


from datetime import date
from app.services.attendance_mail_service import build_preview
from app.services.meeting_service import create_meeting, upsert_attendance

_BODY_TEMPLATE = """
【出　　欠】{status}

【事業所名】{org}

【氏　　名】{name}

【代理者名】{proxy_name}

【代理役職】{proxy_title}

【受任者名（委任代理人）】

【備考】{notes}
"""


def _body(status="出席", org="○○商事", name="山田太郎",
          proxy_name="", proxy_title="", notes=""):
    return _BODY_TEMPLATE.format(
        status=status, org=org, name=name,
        proxy_name=proxy_name, proxy_title=proxy_title, notes=notes)


def test_build_preview_matches_member_and_status(db_session):
    create_member_org = "○○商事"
    create_member(db_session, "A-001", create_member_org, "山田太郎")
    meeting = create_meeting(db_session, "常議員会", date(2026, 7, 20))

    messages = [{"id": "msg-1", "body_text": _body(status="出席(※代理)",
                                                    proxy_name="別所喜三生",
                                                    proxy_title="監査役")}]
    rows = build_preview(db_session, meeting.id, messages)

    assert len(rows) == 1
    row = rows[0]
    assert row.status == "代理"
    assert row.proxy_name == "別所喜三生"
    assert row.proxy_title == "監査役"
    assert row.matched_member is not None
    assert row.matched_member.member_number == "A-001"
    assert row.existing_status is None


def test_build_preview_shows_existing_status_when_already_recorded(db_session):
    member = create_member(db_session, "A-001", "○○商事", "山田太郎")
    meeting = create_meeting(db_session, "常議員会", date(2026, 7, 20))
    upsert_attendance(db_session, meeting.id, member.id, "出席")

    messages = [{"id": "msg-2", "body_text": _body(status="欠席")}]
    rows = build_preview(db_session, meeting.id, messages)

    assert rows[0].existing_status == "出席"
    assert rows[0].status == "欠席"


def test_build_preview_keeps_only_latest_message_per_organization(db_session):
    create_member(db_session, "A-001", "○○商事", "山田太郎")
    meeting = create_meeting(db_session, "常議員会", date(2026, 7, 20))

    # fetch_messagesは受信日時の古い順に返す契約 → 後勝ちで最新のみ残る
    messages = [
        {"id": "msg-old", "body_text": _body(status="出席")},
        {"id": "msg-new", "body_text": _body(status="欠席")},
    ]
    rows = build_preview(db_session, meeting.id, messages)

    assert len(rows) == 1
    assert rows[0].message_id == "msg-new"
    assert rows[0].status == "欠席"


def test_build_preview_unmatched_organization_has_no_member(db_session):
    meeting = create_meeting(db_session, "常議員会", date(2026, 7, 20))
    messages = [{"id": "msg-3", "body_text": _body(org="存在しない会社")}]
    rows = build_preview(db_session, meeting.id, messages)

    assert rows[0].matched_member is None
    assert rows[0].existing_status is None
