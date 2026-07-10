from app.services.committee_service import create_committee
from app.services.member_service import create_member
from app.services.export_service import export_members_csv


def test_export_csv_includes_committee_column(db_session, tmp_path):
    c = create_committee(db_session, "中小・小規模企業委員会", 1)
    create_member(db_session, "A-001", "テスト商事", "山田太郎", committee_id=c.id)
    db_session.commit()

    path = tmp_path / "out.csv"
    count = export_members_csv(db_session, str(path))
    assert count == 1

    content = path.read_text(encoding="utf-8-sig")
    assert "委員会" in content
    assert "中小・小規模企業委員会" in content
