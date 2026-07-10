from app.services.committee_service import (
    create_committee, get_committees, update_committee, delete_committee
)


def test_create_and_get_committees(db_session):
    create_committee(db_session, "総務・運営委員会", 1)
    create_committee(db_session, "地域経済推進委員会", 2)
    committees = get_committees(db_session)
    assert [c.name for c in committees] == ["総務・運営委員会", "地域経済推進委員会"]


def test_get_committees_ordered_by_sort_order(db_session):
    create_committee(db_session, "中小・小規模企業委員会", 2)
    create_committee(db_session, "総務・運営委員会", 1)
    committees = get_committees(db_session)
    assert [c.name for c in committees] == ["総務・運営委員会", "中小・小規模企業委員会"]


def test_update_committee(db_session):
    c = create_committee(db_session, "旧名称", 1)
    update_committee(db_session, c.id, name="新名称")
    committees = get_committees(db_session)
    assert committees[0].name == "新名称"


def test_delete_committee(db_session):
    c = create_committee(db_session, "削除対象", 1)
    delete_committee(db_session, c.id)
    assert get_committees(db_session) == []
