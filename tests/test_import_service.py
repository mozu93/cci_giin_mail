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


def test_import_members_row_error_does_not_lose_other_rows(db_session, monkeypatch):
    """1トランザクションにまとめても、1行の失敗が他行の登録を巻き込まないこと
    （SAVEPOINTによる行単位ロールバックの回帰テスト）。"""
    import app.services.import_service as import_service
    from app.services.member_service import get_members, create_member as real_create_member

    def _fake_create_member(session, member_number, *args, **kwargs):
        if member_number == "A-002":
            raise RuntimeError("想定される行単位のエラー")
        return real_create_member(session, member_number, *args, **kwargs)

    monkeypatch.setattr(import_service, "create_member", _fake_create_member)

    ok_row = ["A-001", "○○商事", "", "", "山田 太郎", "", "", "yamada@example.com", ""]
    bad_row = ["A-002", "△△産業", "", "", "鈴木 花子", "", "", "suzuki@example.com", ""]

    result = import_members(db_session, [ok_row, bad_row], COLUMN_MAP,
                            changed_by="管理者")

    assert result["created"] == 1
    assert len(result["errors"]) == 1

    members = get_members(db_session, active_only=False)
    assert [m.member_number for m in members] == ["A-001"]
