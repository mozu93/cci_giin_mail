from app.services.position_service import (
    create_position, update_position, delete_position, get_positions
)


def test_create_position(db_session):
    pos = create_position(db_session, "会頭", 1)
    assert pos.id is not None
    assert pos.name == "会頭"


def test_get_positions_sorted(db_session):
    create_position(db_session, "議員", 10)
    create_position(db_session, "会頭", 1)
    positions = get_positions(db_session)
    assert positions[0].name == "会頭"
    assert positions[1].name == "議員"


def test_delete_position(db_session):
    pos = create_position(db_session, "会頭", 1)
    delete_position(db_session, pos.id)
    assert len(get_positions(db_session)) == 0
