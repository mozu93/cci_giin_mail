# tests/test_settings_position_widget.py
from PyQt6.QtWidgets import QMessageBox
from app.database.models import Member
from app.services.position_service import get_positions, create_position
from app.services.member_service import create_member


def test_add_update_delete_position(qtbot, monkeypatch, db_session):
    monkeypatch.setattr("app.ui.settings_tab.get_session", lambda: db_session)
    monkeypatch.setattr(
        QMessageBox, "question",
        staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes))

    from app.ui.settings_tab import _PositionWidget
    w = _PositionWidget()
    qtbot.addWidget(w)

    w._name.setText("会頭")
    w._add()
    assert w._table.rowCount() == 1
    assert w._table.item(0, 0).text() == "会頭"

    w._table.selectRow(0)
    w._name.setText("会頭（改）")
    w._update()
    assert w._table.item(0, 0).text() == "会頭（改）"

    w._table.selectRow(0)
    w._delete()
    assert w._table.rowCount() == 0
    assert get_positions(db_session) == []


def test_delete_position_with_members_warns_and_nulls_position_id(
        qtbot, monkeypatch, db_session):
    monkeypatch.setattr("app.ui.settings_tab.get_session", lambda: db_session)
    monkeypatch.setattr(
        QMessageBox, "question",
        staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes))

    position = create_position(db_session, "議員", 1)
    member = create_member(
        db_session, "B-001", "○○商工会", "テスト太郎",
        position_id=position.id)
    member_id = member.id

    from app.ui.settings_tab import _PositionWidget
    w = _PositionWidget()
    qtbot.addWidget(w)

    assert w._table.rowCount() == 1
    w._table.selectRow(0)
    w._delete()

    assert w._table.rowCount() == 0
    assert get_positions(db_session) == []

    db_session.expire_all()
    updated_member = db_session.get(Member, member_id)
    assert updated_member.position_id is None


def test_move_up_and_down_reorders_positions(qtbot, monkeypatch, db_session):
    monkeypatch.setattr("app.ui.settings_tab.get_session", lambda: db_session)

    create_position(db_session, "会頭", 1)
    create_position(db_session, "副会頭", 2)
    create_position(db_session, "議員", 3)

    from app.ui.settings_tab import _PositionWidget
    w = _PositionWidget()
    qtbot.addWidget(w)

    names = [w._table.item(i, 0).text() for i in range(w._table.rowCount())]
    assert names == ["会頭", "副会頭", "議員"]

    w._table.selectRow(2)  # 議員
    w._move(-1)  # 上へ

    names_after = [w._table.item(i, 0).text() for i in range(w._table.rowCount())]
    assert names_after == ["会頭", "議員", "副会頭"]

    positions = get_positions(db_session)
    assert [p.sort_order for p in positions] == [1, 2, 3]


def test_move_up_at_top_row_does_nothing(qtbot, monkeypatch, db_session):
    monkeypatch.setattr("app.ui.settings_tab.get_session", lambda: db_session)
    create_position(db_session, "会頭", 1)
    create_position(db_session, "議員", 2)

    from app.ui.settings_tab import _PositionWidget
    w = _PositionWidget()
    qtbot.addWidget(w)

    w._table.selectRow(0)
    w._move(-1)

    names = [w._table.item(i, 0).text() for i in range(w._table.rowCount())]
    assert names == ["会頭", "議員"]
