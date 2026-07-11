from app.services.staff_service import (
    create_staff, get_active_staff, get_all_staff,
    get_staff_by_name, set_active, set_admin,
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


def test_create_staff_defaults_to_non_admin(db_session):
    s = create_staff(db_session, "山田")
    assert s.is_admin is False


def test_create_staff_with_admin_flag(db_session):
    s = create_staff(db_session, "水谷", is_admin=True)
    assert s.is_admin is True


def test_set_admin_toggles_flag(db_session):
    s = create_staff(db_session, "山田")
    set_admin(db_session, s.id, True)
    db_session.refresh(s)
    assert s.is_admin is True
    set_admin(db_session, s.id, False)
    db_session.refresh(s)
    assert s.is_admin is False
