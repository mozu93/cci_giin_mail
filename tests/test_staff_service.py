from app.services.staff_service import (
    create_staff, get_active_staff, set_active
)


def test_create_and_get_staff(db_session):
    s = create_staff(db_session, "田中")
    staff = get_active_staff(db_session)
    assert len(staff) == 1
    assert staff[0].name == "田中"


def test_inactive_staff_excluded(db_session):
    s = create_staff(db_session, "田中")
    set_active(db_session, s.id, False)
    assert len(get_active_staff(db_session)) == 0
