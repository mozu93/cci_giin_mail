# tests/test_settings_committee_widget.py
from PyQt6.QtWidgets import QMessageBox
from app.database.models import Member
from app.services.committee_service import get_committees, create_committee
from app.services.member_service import create_member


def test_add_update_delete_committee(qtbot, monkeypatch, db_session):
    monkeypatch.setattr("app.ui.settings_tab.get_session", lambda: db_session)
    monkeypatch.setattr(
        QMessageBox, "question",
        staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes))

    from app.ui.settings_tab import _CommitteeWidget
    w = _CommitteeWidget()
    qtbot.addWidget(w)

    w._name.setText("総務・運営委員会")
    w._add()
    assert w._table.rowCount() == 1
    assert w._table.item(0, 0).text() == "総務・運営委員会"

    w._table.selectRow(0)
    w._name.setText("総務・運営委員会（改）")
    w._update()
    assert w._table.item(0, 0).text() == "総務・運営委員会（改）"

    w._table.selectRow(0)
    w._delete()
    assert w._table.rowCount() == 0
    assert get_committees(db_session) == []


def test_delete_committee_with_members_warns_and_nulls_committee_id(
        qtbot, monkeypatch, db_session):
    monkeypatch.setattr("app.ui.settings_tab.get_session", lambda: db_session)
    monkeypatch.setattr(
        QMessageBox, "question",
        staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes))

    committee = create_committee(db_session, "広報委員会", 1)
    member = create_member(
        db_session, "B-001", "○○商工会", "テスト太郎",
        committee_id=committee.id)
    member_id = member.id

    from app.ui.settings_tab import _CommitteeWidget
    w = _CommitteeWidget()
    qtbot.addWidget(w)

    assert w._table.rowCount() == 1
    w._table.selectRow(0)
    w._delete()

    assert w._table.rowCount() == 0
    assert get_committees(db_session) == []

    db_session.expire_all()
    updated_member = db_session.get(Member, member_id)
    assert updated_member.committee_id is None


def test_position_committee_widget_refresh_reloads_committees_added_elsewhere(
        qtbot, monkeypatch, db_session):
    monkeypatch.setattr("app.ui.settings_tab.get_session", lambda: db_session)

    from app.ui.settings_tab import _PositionCommitteeWidget
    w = _PositionCommitteeWidget()
    qtbot.addWidget(w)
    assert w._committee_widget._table.rowCount() == 0

    # 他のタブ(名簿インポート等)がこのウィジェットを介さずに委員会を追加した状況を再現
    create_committee(db_session, "総務・運営委員会", 1)

    w.refresh()
    assert w._committee_widget._table.rowCount() == 1
    assert w._committee_widget._table.item(0, 0).text() == "総務・運営委員会"
