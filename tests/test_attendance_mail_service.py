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
