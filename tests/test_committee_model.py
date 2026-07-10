from app.database.models import Committee, Member


def test_committee_model_fields(db_session):
    c = Committee(name="総務・運営委員会", sort_order=1)
    db_session.add(c)
    db_session.commit()
    assert c.id is not None


def test_member_committee_relationship(db_session):
    c = Committee(name="地域経済推進委員会", sort_order=2)
    db_session.add(c)
    db_session.commit()

    m = Member(member_number="A-001", organization_name="テスト商事",
               name="山田太郎", committee_id=c.id)
    db_session.add(m)
    db_session.commit()

    assert m.committee.name == "地域経済推進委員会"
    assert m in c.members
