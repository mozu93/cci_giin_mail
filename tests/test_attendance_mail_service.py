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


def test_normalize_org_name_strips_stray_question_mark_from_lost_characters():
    # '?' はメール送信元でデコードできず失われた文字（㈱記号や異体字漢字など）の印。
    assert normalize_org_name("三菱ケミカル?東海事業所") == normalize_org_name(
        "三菱ケミカル（株）東海事業所")


def test_normalize_org_name_strips_yugen_gaisha_suffix_variants():
    assert normalize_org_name("有限会社トヨタ不動産") == normalize_org_name(
        "（有）トヨタ不動産")
    assert normalize_org_name("㈲トヨタ不動産") == normalize_org_name(
        "(有)トヨタ不動産")


def test_normalize_org_name_unifies_kyuujitai_kanji_variant():
    # 「鐵」は「鉄」の旧字体。社名の正式表記が旧字体でも、メール側が
    # 新字体で書かれるケースがあるため統一する。
    assert normalize_org_name("三重機械鐵工株式会社") == normalize_org_name(
        "三重機械鉄工（株）")


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


def test_match_member_matches_yugen_gaisha_abbreviation(db_session):
    create_member(db_session, "A-001", "（有）トヨタ不動産", "豊田太郎")
    m = match_member(db_session, "有限会社トヨタ不動産")
    assert m is not None
    assert m.member_number == "A-001"


def test_match_member_matches_kyuujitai_kanji_variant(db_session):
    create_member(db_session, "A-001", "三重機械鐵工（株）", "三重次郎")
    m = match_member(db_session, "三重機械鉄工株式会社")
    assert m is not None
    assert m.member_number == "A-001"


def test_match_member_returns_none_when_no_match(db_session):
    create_member(db_session, "A-001", "○○商事", "山田太郎")
    assert match_member(db_session, "存在しない会社") is None


def test_match_member_returns_none_when_ambiguous(db_session):
    create_member(db_session, "A-001", "山田商事", "山田太郎")
    create_member(db_session, "A-002", "山田商事", "山田次郎")
    assert match_member(db_session, "山田商事") is None


def test_match_member_matches_when_mail_org_name_is_contained_in_member_org_name(db_session):
    # メールは支店名を省略した表記、会員データはフル表記のケース
    create_member(db_session, "A-001", "（株）近鉄百貨店四日市店", "清水一広")
    m = match_member(db_session, "近鉄百貨店")
    assert m is not None
    assert m.member_number == "A-001"


def test_match_member_containment_returns_none_when_ambiguous(db_session):
    create_member(db_session, "A-001", "近鉄百貨店四日市店", "清水一広")
    create_member(db_session, "A-002", "近鉄百貨店津店", "田中次郎")
    assert match_member(db_session, "近鉄百貨店") is None


def test_match_member_prefers_saved_alias_over_heuristics(db_session):
    """通常の突合ロジックが選ぶ会員と異なっていても、保存済みの紐付けを優先する
    （手動で紐付けを修正した結果を常に尊重するため）。"""
    from app.services.attendance_mail_service import upsert_alias
    heuristic_pick = create_member(db_session, "A-001", "○○商事", "山田太郎")
    manually_assigned = create_member(db_session, "A-002", "△△興業", "佐藤次郎")
    upsert_alias(db_session, "○○商事", manually_assigned.id)
    db_session.commit()

    m = match_member(db_session, "○○商事")
    assert m is not None
    assert m.member_number == "A-002"


def test_upsert_alias_overwrites_wrong_mapping(db_session):
    from app.services.attendance_mail_service import upsert_alias
    from app.database.models import AttendanceMailAlias
    wrong = create_member(db_session, "A-001", "○○商事", "山田太郎")
    correct = create_member(db_session, "A-002", "○○商事西支店", "山田次郎")

    upsert_alias(db_session, "○○商事西", wrong.id)
    db_session.commit()
    upsert_alias(db_session, "○○商事西", correct.id)
    db_session.commit()

    aliases = db_session.query(AttendanceMailAlias).all()
    assert len(aliases) == 1
    assert aliases[0].member_id == correct.id


from datetime import date, datetime
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
                                                    proxy_title="監査役"),
                 "received_at": datetime(2026, 7, 10, 9, 0, 0)}]
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

    messages = [{"id": "msg-2", "body_text": _body(status="欠席"),
                 "received_at": datetime(2026, 7, 10, 9, 0, 0)}]
    rows = build_preview(db_session, meeting.id, messages)

    assert rows[0].existing_status == "出席"
    assert rows[0].status == "欠席"


def test_build_preview_keeps_only_latest_message_per_organization(db_session):
    create_member(db_session, "A-001", "○○商事", "山田太郎")
    meeting = create_meeting(db_session, "常議員会", date(2026, 7, 20))

    # fetch_messagesは受信日時の古い順に返す契約 → 後勝ちで最新のみ残る
    messages = [
        {"id": "msg-old", "body_text": _body(status="出席"),
         "received_at": datetime(2026, 7, 5, 9, 0, 0)},
        {"id": "msg-new", "body_text": _body(status="欠席"),
         "received_at": datetime(2026, 7, 10, 9, 0, 0)},
    ]
    rows = build_preview(db_session, meeting.id, messages)

    assert len(rows) == 1
    assert rows[0].message_id == "msg-new"
    assert rows[0].status == "欠席"


def test_build_preview_unmatched_organization_has_no_member(db_session):
    meeting = create_meeting(db_session, "常議員会", date(2026, 7, 20))
    messages = [{"id": "msg-3", "body_text": _body(org="存在しない会社"),
                 "received_at": datetime(2026, 7, 10, 9, 0, 0)}]
    rows = build_preview(db_session, meeting.id, messages)

    assert rows[0].matched_member is None
    assert rows[0].existing_status is None


def test_build_preview_keeps_both_when_org_name_extraction_fails_for_multiple_mails(
        db_session):
    """事業所名を抽出できないメールが複数あっても、互いに上書きして
    消えないこと（正規化キーが空文字同士で衝突し、片方が一覧から
    見えなくなって取りこぼされるのを防ぐ回帰テスト）。"""
    meeting = create_meeting(db_session, "常議員会", date(2026, 7, 20))
    messages = [
        {"id": "msg-broken-1", "body_text": "本文の形式が想定と異なるメール1",
         "received_at": datetime(2026, 7, 5, 9, 0, 0)},
        {"id": "msg-broken-2", "body_text": "本文の形式が想定と異なるメール2",
         "received_at": datetime(2026, 7, 10, 9, 0, 0)},
    ]
    rows = build_preview(db_session, meeting.id, messages)

    assert len(rows) == 2
    assert {r.message_id for r in rows} == {"msg-broken-1", "msg-broken-2"}


import pytest
from app.services.attendance_mail_service import fetch_messages


class _FakeResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload
        self.text = str(payload)

    def json(self):
        return self._payload


def test_fetch_messages_resolves_folder_and_filters(monkeypatch):
    monkeypatch.setattr(
        "app.services.attendance_mail_service.get_access_token",
        lambda cfg: "dummy-token")

    def fake_get(url, headers=None, params=None, timeout=None):
        if url.endswith("/me/mailFolders"):
            assert params["$filter"] == "displayName eq '常議員会出欠'"
            return _FakeResponse(200, {"value": [{"id": "folder-1"}]})
        if url.endswith("/me/mailFolders/folder-1/messages"):
            assert params["$filter"] == "receivedDateTime gt 2026-07-01T00:00:00Z"
            return _FakeResponse(200, {"value": [
                {"id": "msg-1", "subject": "常議員会出欠連絡",
                 "receivedDateTime": "2026-07-15T10:00:00Z",
                 "body": {"content": "本文1"}},
                {"id": "msg-2", "subject": "別件のお知らせ",
                 "receivedDateTime": "2026-07-16T10:00:00Z",
                 "body": {"content": "本文2"}},
            ]})
        raise AssertionError(f"unexpected url: {url}")

    monkeypatch.setattr("app.services.attendance_mail_service.requests.get", fake_get)

    messages = fetch_messages({}, "常議員会出欠", "出欠連絡", exclude_ids=set(),
                              since=datetime(2026, 7, 1))

    assert len(messages) == 1
    assert messages[0]["id"] == "msg-1"
    assert messages[0]["body_text"] == "本文1"
    assert messages[0]["received_at"] == datetime(2026, 7, 15, 10, 0, 0)


def test_fetch_messages_excludes_already_processed(monkeypatch):
    monkeypatch.setattr(
        "app.services.attendance_mail_service.get_access_token",
        lambda cfg: "dummy-token")

    def fake_get(url, headers=None, params=None, timeout=None):
        if url.endswith("/me/mailFolders"):
            return _FakeResponse(200, {"value": [{"id": "folder-1"}]})
        return _FakeResponse(200, {"value": [
            {"id": "msg-1", "subject": "件名",
             "receivedDateTime": "2026-07-15T10:00:00Z",
             "body": {"content": "本文1"}},
        ]})

    monkeypatch.setattr("app.services.attendance_mail_service.requests.get", fake_get)

    messages = fetch_messages({}, "常議員会出欠", "", exclude_ids={"msg-1"},
                              since=datetime(2000, 1, 1))

    assert messages == []


def test_fetch_messages_resolves_nested_subfolder(monkeypatch):
    """トップレベルに無く、他フォルダの下（サブフォルダ）にある場合も見つけられること。"""
    monkeypatch.setattr(
        "app.services.attendance_mail_service.get_access_token",
        lambda cfg: "dummy-token")

    def fake_get(url, headers=None, params=None, timeout=None):
        if url.endswith("/me/mailFolders") and "$filter" in (params or {}):
            assert params["$filter"] == "displayName eq '常議員会出欠連絡'"
            return _FakeResponse(200, {"value": []})
        if url.endswith("/me/mailFolders"):
            return _FakeResponse(200, {"value": [
                {"id": "inbox-1", "displayName": "受信トレイ"},
            ]})
        if url.endswith("/me/mailFolders/inbox-1/childFolders"):
            return _FakeResponse(200, {"value": [
                {"id": "folder-1", "displayName": "常議員会出欠連絡"},
            ]})
        if url.endswith("/me/mailFolders/folder-1/messages"):
            return _FakeResponse(200, {"value": [
                {"id": "msg-1", "subject": "常議員会出欠連絡",
                 "receivedDateTime": "2026-07-15T10:00:00Z",
                 "body": {"content": "本文1"}},
            ]})
        raise AssertionError(f"unexpected url/params: {url} {params}")

    monkeypatch.setattr("app.services.attendance_mail_service.requests.get", fake_get)

    messages = fetch_messages({}, "常議員会出欠連絡", "", exclude_ids=set(),
                              since=datetime(2026, 7, 1))

    assert len(messages) == 1
    assert messages[0]["id"] == "msg-1"


def test_fetch_messages_raises_when_folder_not_found(monkeypatch):
    monkeypatch.setattr(
        "app.services.attendance_mail_service.get_access_token",
        lambda cfg: "dummy-token")

    def fake_get(url, headers=None, params=None, timeout=None):
        return _FakeResponse(200, {"value": []})

    monkeypatch.setattr("app.services.attendance_mail_service.requests.get", fake_get)

    with pytest.raises(ValueError, match="見つかりません"):
        fetch_messages({}, "存在しないフォルダ", "", exclude_ids=set(),
                       since=datetime(2000, 1, 1))


from app.services.attendance_mail_service import commit_rows
from app.database.models import ProcessedAttendanceMail, AttendanceRecord


def test_commit_rows_applies_selected_rows_and_records_message_id(db_session):
    from app.services.member_service import create_member
    member = create_member(db_session, "A-001", "○○商事", "山田太郎")
    meeting = create_meeting(db_session, "常議員会", date(2026, 7, 20))

    messages = [{"id": "msg-1", "body_text": _body(status="出席"),
                 "received_at": datetime(2026, 7, 10, 9, 0, 0)}]
    rows = build_preview(db_session, meeting.id, messages)

    result = commit_rows(db_session, meeting.id, rows,
                         selected_member_by_index={0: member.id})

    assert result["applied"] == 1
    assert result["skipped"] == 0
    record = (db_session.query(AttendanceRecord)
             .filter_by(meeting_id=meeting.id, member_id=member.id).first())
    assert record.status == "出席"
    processed = db_session.query(ProcessedAttendanceMail).all()
    assert len(processed) == 1
    assert processed[0].message_id == "msg-1"
    assert processed[0].member_id == member.id


def test_commit_rows_records_member_id_for_duplicate_org_name_variants(db_session):
    """同じ会社が表記違いで複数回メールを送り、それぞれ別行として反映された
    場合でも、ProcessedAttendanceMailに会員IDが記録され、後から「どの会員に
    複数回反映されたか」をログから追跡できること。"""
    from app.services.member_service import create_member
    from app.services.attendance_mail_service import upsert_alias
    member = create_member(db_session, "A-001", "中部電力パワーグリッド株式会社", "鈴木一郎")
    meeting = create_meeting(db_session, "常議員会", date(2026, 7, 20))
    upsert_alias(db_session, "中部電力パワーグリッド四日市支社", member.id)

    messages = [
        {"id": "msg-1", "body_text": _body(org="中部電力パワーグリッド株式会社", status="出席"),
         "received_at": datetime(2026, 7, 10, 9, 0, 0)},
        {"id": "msg-2", "body_text": _body(
            org="中部電力パワーグリッド四日市支社", status="出席"),
         "received_at": datetime(2026, 7, 10, 10, 0, 0)},
    ]
    rows = build_preview(db_session, meeting.id, messages)
    assert len(rows) == 2  # 表記違いのため別行として扱われる

    result = commit_rows(
        db_session, meeting.id, rows,
        selected_member_by_index={0: member.id, 1: member.id})

    assert result["applied"] == 2
    assert result["skipped"] == 0
    processed = db_session.query(ProcessedAttendanceMail).order_by(
        ProcessedAttendanceMail.message_id).all()
    assert len(processed) == 2
    assert all(p.member_id == member.id for p in processed)

    assert len(result["duplicates"]) == 1
    dup = result["duplicates"][0]
    assert dup["member_id"] == member.id
    assert dup["organization_name"] == "中部電力パワーグリッド株式会社"
    assert dup["count"] == 2
    assert set(dup["org_names_raw"]) == {
        "中部電力パワーグリッド株式会社", "中部電力パワーグリッド四日市支社"}


def test_commit_rows_reports_no_duplicates_when_all_members_unique(db_session):
    from app.services.member_service import create_member
    member = create_member(db_session, "A-001", "○○商事", "山田太郎")
    meeting = create_meeting(db_session, "常議員会", date(2026, 7, 20))
    messages = [{"id": "msg-1", "body_text": _body(status="出席"),
                 "received_at": datetime(2026, 7, 10, 9, 0, 0)}]
    rows = build_preview(db_session, meeting.id, messages)

    result = commit_rows(db_session, meeting.id, rows,
                         selected_member_by_index={0: member.id})

    assert result["duplicates"] == []


def test_commit_rows_skips_rows_without_selected_member(db_session):
    meeting = create_meeting(db_session, "常議員会", date(2026, 7, 20))
    messages = [{"id": "msg-1", "body_text": _body(org="存在しない会社"),
                 "received_at": datetime(2026, 7, 10, 9, 0, 0)}]
    rows = build_preview(db_session, meeting.id, messages)

    result = commit_rows(db_session, meeting.id, rows, selected_member_by_index={})

    assert result["applied"] == 0
    assert result["skipped"] == 1
    assert db_session.query(ProcessedAttendanceMail).count() == 0


from app.services.attendance_mail_service import get_since_datetime, AttendanceMailRow


def test_get_since_datetime_defaults_to_first_of_meeting_month_when_no_prior_import(db_session):
    meeting = create_meeting(db_session, "常議員会", date(2026, 7, 20))
    since = get_since_datetime(db_session, meeting.id)
    assert since == datetime(2026, 7, 1)


def test_get_since_datetime_ignores_already_processed_mail(db_session):
    """反映済みメールがあっても検索開始日時は開催月の1日のまま進めない。

    反映されなかった（会員未選択・突合不可の）メールを、反映済みメールより
    受信日時が前だからという理由で次回検索から取りこぼさないようにするため。
    反映済みメールの重複表示防止はexclude_ids側の責務。
    """
    from app.services.member_service import create_member
    member = create_member(db_session, "A-001", "○○商事", "山田太郎")
    meeting = create_meeting(db_session, "常議員会", date(2026, 7, 20))
    db_session.add(ProcessedAttendanceMail(
        message_id="msg-old", meeting_id=meeting.id,
        received_at=datetime(2026, 7, 5, 9, 0, 0)))
    db_session.add(ProcessedAttendanceMail(
        message_id="msg-new", meeting_id=meeting.id,
        received_at=datetime(2026, 7, 10, 12, 0, 0)))
    db_session.commit()

    since = get_since_datetime(db_session, meeting.id)
    assert since == datetime(2026, 7, 1)


def test_commit_rows_saves_alias_so_next_import_auto_matches(db_session):
    """一度手動選択でマッチングさせた事業所名は、次回以降は自動で同じ会員に
    マッチングされる（誤マッチングで手動選択したケースを想定）。"""
    # 会員データとメール記載の表記が包含関係にも無く、完全一致もしない例
    member = create_member(db_session, "A-001", "丸丸物産グループ", "山田太郎")
    meeting = create_meeting(db_session, "常議員会", date(2026, 7, 20))

    # 1回目: 自動マッチングは失敗するが、手動で選択して反映
    messages = [{"id": "msg-1", "body_text": _body(org="○○商事"),
                 "received_at": datetime(2026, 7, 10, 9, 0, 0)}]
    rows = build_preview(db_session, meeting.id, messages)
    assert rows[0].matched_member is None
    commit_rows(db_session, meeting.id, rows, {0: member.id})

    # 2回目: 同じ表記のメールは自動的に同じ会員にマッチングされる
    messages2 = [{"id": "msg-2", "body_text": _body(org="○○商事"),
                  "received_at": datetime(2026, 7, 15, 9, 0, 0)}]
    rows2 = build_preview(db_session, meeting.id, messages2)
    assert rows2[0].matched_member is not None
    assert rows2[0].matched_member.member_number == "A-001"


from app.services.attendance_mail_service import (
    list_aliases, delete_alias, update_alias_member, upsert_alias)
from app.database.models import AttendanceMailAlias


def test_list_aliases_returns_saved_aliases_with_member(db_session):
    member = create_member(db_session, "A-001", "○○商事", "山田太郎")
    upsert_alias(db_session, "○○商事株式会社", member.id)
    db_session.commit()

    aliases = list_aliases(db_session)
    assert len(aliases) == 1
    assert aliases[0].member.member_number == "A-001"


def test_delete_alias_removes_mapping_and_falls_back_to_heuristics(db_session):
    member = create_member(db_session, "A-001", "○○商事", "山田太郎")
    other = create_member(db_session, "A-002", "○○商事別会社", "佐藤次郎")
    upsert_alias(db_session, "○○商事", other.id)
    db_session.commit()
    alias_id = db_session.query(AttendanceMailAlias).first().id

    delete_alias(db_session, alias_id)

    assert db_session.query(AttendanceMailAlias).count() == 0
    # 紐付け削除後は通常の突合（完全一致）にフォールバックする
    m = match_member(db_session, "○○商事")
    assert m is not None
    assert m.member_number == "A-001"


def test_update_alias_member_corrects_wrong_mapping(db_session):
    wrong = create_member(db_session, "A-001", "○○商事", "山田太郎")
    correct = create_member(db_session, "A-002", "○○商事別会社", "佐藤次郎")
    upsert_alias(db_session, "○○商事", wrong.id)
    db_session.commit()
    alias_id = db_session.query(AttendanceMailAlias).first().id

    update_alias_member(db_session, alias_id, correct.id)

    m = match_member(db_session, "○○商事")
    assert m is not None
    assert m.member_number == "A-002"


def test_commit_rows_skips_rows_with_unrecognized_status(db_session):
    from app.services.member_service import create_member
    member = create_member(db_session, "A-001", "○○商事", "山田太郎")
    meeting = create_meeting(db_session, "常議員会", date(2026, 7, 20))
    row = AttendanceMailRow(
        message_id="msg-1", org_name_raw="○○商事", name_raw="山田太郎",
        status="",  # STATUS_MAPに無い値だった場合の想定（空文字）
        proxy_title="", proxy_name="", notes="",
        matched_member=member, existing_status=None,
        received_at=datetime(2026, 7, 10))

    result = commit_rows(db_session, meeting.id, [row], {0: member.id})

    assert result["applied"] == 0
    assert result["skipped"] == 1
    assert db_session.query(ProcessedAttendanceMail).count() == 0
