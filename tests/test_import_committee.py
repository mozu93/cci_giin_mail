import app.services.import_service as import_service
from app.services.import_service import import_members
from app.services.committee_service import get_committees, create_committee
from app.services.member_service import get_members, create_member as real_create_member


def test_import_creates_new_committee_from_name(db_session):
    rows = [["A-001", "テスト商事", "山田太郎", "総務・運営委員会"]]
    column_map = {
        "member_number": 0, "organization_name": 1,
        "name": 2, "committee_name": 3,
    }
    result = import_members(db_session, rows, column_map, changed_by="担当者A")
    assert result["created"] == 1

    committees = get_committees(db_session)
    assert [c.name for c in committees] == ["総務・運営委員会"]

    member = get_members(db_session)[0]
    assert member.committee_id == committees[0].id


def test_import_maps_to_existing_committee(db_session):
    c = create_committee(db_session, "地域経済推進委員会", 1)
    rows = [["A-002", "テスト工業", "鈴木花子", "地域経済推進委員会"]]
    column_map = {
        "member_number": 0, "organization_name": 1,
        "name": 2, "committee_name": 3,
    }
    import_members(db_session, rows, column_map, changed_by="担当者A")

    assert len(get_committees(db_session)) == 1  # 新規作成されない
    member = get_members(db_session)[0]
    assert member.committee_id == c.id


def test_import_row_failure_does_not_leak_unused_committee(db_session, monkeypatch):
    """新しい委員会名を初めて使う行の会員登録が失敗した場合、その委員会マスタ
    行だけが未使用のまま残ってはならない（SAVEPOINT境界の回帰テスト）。"""

    def _fake_create_member(session, member_number, *args, **kwargs):
        if member_number == "A-001":
            raise RuntimeError("想定される行単位のエラー")
        return real_create_member(session, member_number, *args, **kwargs)

    monkeypatch.setattr(import_service, "create_member", _fake_create_member)

    rows = [["A-001", "テスト商事", "山田太郎", "新設委員会"]]
    column_map = {
        "member_number": 0, "organization_name": 1,
        "name": 2, "committee_name": 3,
    }
    result = import_members(db_session, rows, column_map, changed_by="担当者A")

    assert result["created"] == 0
    assert len(result["errors"]) == 1
    assert get_committees(db_session) == []


def test_import_later_row_still_gets_committee_after_earlier_row_fails(
        db_session, monkeypatch):
    """委員会名を初めて使う行が失敗しても、同じ委員会名を使う後続行では
    正しく委員会が新規作成・紐付けされること。"""

    def _fake_create_member(session, member_number, *args, **kwargs):
        if member_number == "A-001":
            raise RuntimeError("想定される行単位のエラー")
        return real_create_member(session, member_number, *args, **kwargs)

    monkeypatch.setattr(import_service, "create_member", _fake_create_member)

    rows = [
        ["A-001", "テスト商事", "山田太郎", "新設委員会"],
        ["A-002", "テスト工業", "鈴木花子", "新設委員会"],
    ]
    column_map = {
        "member_number": 0, "organization_name": 1,
        "name": 2, "committee_name": 3,
    }
    result = import_members(db_session, rows, column_map, changed_by="担当者A")

    assert result["created"] == 1
    assert len(result["errors"]) == 1

    committees = get_committees(db_session)
    assert [c.name for c in committees] == ["新設委員会"]
    member = get_members(db_session)[0]
    assert member.member_number == "A-002"
    assert member.committee_id == committees[0].id
