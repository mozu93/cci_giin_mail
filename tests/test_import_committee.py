from app.services.import_service import import_members
from app.services.committee_service import get_committees, create_committee
from app.services.member_service import get_members


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
