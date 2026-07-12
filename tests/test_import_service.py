from app.services.import_service import load_member_file, import_members


COLUMN_MAP = {
    "member_number":    0,
    "organization_name": 1,
    "organization_kana": 2,
    "title":            3,
    "name":             4,
    "name_kana":        5,
    "email_1_address":  7,
    "email_1_label":    8,
    "email_2_address":  9,
    "email_2_label":    10,
}


def test_load_member_file_returns_headers_and_rows(sample_excel):
    headers, rows = load_member_file(sample_excel)
    assert len(headers) == 11
    assert headers[0] == "会員番号"
    assert len(rows) == 2


def test_import_members_creates_new(db_session, sample_excel):
    _, rows = load_member_file(sample_excel)
    result = import_members(db_session, rows, COLUMN_MAP, changed_by="管理者")
    assert result["created"] == 2
    assert result["updated"] == 0
    assert result["errors"] == []


def test_import_members_updates_existing(db_session, sample_excel):
    _, rows = load_member_file(sample_excel)
    import_members(db_session, rows, COLUMN_MAP, changed_by="管理者")
    # 2回目は同じ会員番号なのでupdateになる
    result = import_members(db_session, rows, COLUMN_MAP, changed_by="管理者")
    assert result["created"] == 0
    assert result["updated"] == 2


def test_import_members_sets_email_addresses(db_session, sample_excel):
    from app.services.member_service import get_members
    _, rows = load_member_file(sample_excel)
    import_members(db_session, rows, COLUMN_MAP, changed_by="管理者")
    members = get_members(db_session, active_only=False)
    suzuki = next(m for m in members if m.member_number == "A-002")
    assert len(suzuki.email_addresses) == 2


def test_import_members_converts_kana_to_halfwidth(db_session, sample_excel):
    from app.services.member_service import get_members
    _, rows = load_member_file(sample_excel)
    import_members(db_session, rows, COLUMN_MAP, changed_by="管理者")
    members = get_members(db_session, active_only=False)
    yamada = next(m for m in members if m.member_number == "A-001")
    assert yamada.organization_kana == "ﾏﾙﾏﾙｼｮｳｼﾞ"
    assert yamada.name_kana == "ﾔﾏﾀﾞ ﾀﾛｳ"
