# tests/test_settings_committee_widget.py
from PyQt6.QtWidgets import QMessageBox
from app.services.committee_service import get_committees


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
