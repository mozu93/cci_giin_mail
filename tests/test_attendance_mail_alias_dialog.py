from app.services.member_service import create_member
from app.services.attendance_mail_service import upsert_alias
from app.database.models import AttendanceMailAlias


def test_dialog_lists_existing_aliases(qtbot, monkeypatch, db_session):
    monkeypatch.setattr(
        "app.ui.dialogs.attendance_mail_alias_dialog.get_session",
        lambda: db_session)
    member = create_member(db_session, "A-001", "○○商事", "山田太郎")
    upsert_alias(db_session, "○○商事株式会社", member.id)
    db_session.commit()

    from app.ui.dialogs.attendance_mail_alias_dialog import AttendanceMailAliasDialog
    dlg = AttendanceMailAliasDialog()
    qtbot.addWidget(dlg)

    assert dlg._table.rowCount() == 1
    assert dlg._table.item(0, dlg._COL_ORG).text() == "○○商事株式会社"
    combo = dlg._table.cellWidget(0, dlg._COL_MEMBER)
    assert combo.currentData() == member.id


def test_changing_member_combo_updates_alias(qtbot, monkeypatch, db_session):
    monkeypatch.setattr(
        "app.ui.dialogs.attendance_mail_alias_dialog.get_session",
        lambda: db_session)
    wrong = create_member(db_session, "A-001", "○○商事", "山田太郎")
    correct = create_member(db_session, "A-002", "○○商事別会社", "佐藤次郎")
    upsert_alias(db_session, "○○商事", wrong.id)
    db_session.commit()

    from app.ui.dialogs.attendance_mail_alias_dialog import AttendanceMailAliasDialog
    dlg = AttendanceMailAliasDialog()
    qtbot.addWidget(dlg)

    combo = dlg._table.cellWidget(0, dlg._COL_MEMBER)
    correct_index = combo.findData(correct.id)
    combo.setCurrentIndex(correct_index)

    alias = db_session.query(AttendanceMailAlias).first()
    assert alias.member_id == correct.id


def test_delete_button_removes_alias(qtbot, monkeypatch, db_session):
    monkeypatch.setattr(
        "app.ui.dialogs.attendance_mail_alias_dialog.get_session",
        lambda: db_session)
    member = create_member(db_session, "A-001", "○○商事", "山田太郎")
    upsert_alias(db_session, "○○商事", member.id)
    db_session.commit()

    from PyQt6.QtWidgets import QMessageBox
    monkeypatch.setattr(
        QMessageBox, "question",
        staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes))

    from app.ui.dialogs.attendance_mail_alias_dialog import AttendanceMailAliasDialog
    dlg = AttendanceMailAliasDialog()
    qtbot.addWidget(dlg)

    btn_delete = dlg._table.cellWidget(0, dlg._COL_DELETE)
    btn_delete.click()

    assert db_session.query(AttendanceMailAlias).count() == 0
    assert dlg._table.rowCount() == 0
