from PyQt6.QtWidgets import QMessageBox


def test_save_blocks_invalid_email_format(qtbot, db_session, monkeypatch):
    from app.ui.dialogs.member_edit_dialog import MemberEditDialog
    dlg = MemberEditDialog(db_session, staff_name="担当者A")
    qtbot.addWidget(dlg)

    dlg._member_number.setText("A-200")
    dlg._org_name.setText("テスト商事")
    dlg._name.setText("山田太郎")
    dlg._email_rows[0][0].setText("invalid-address")

    warning_calls = []
    monkeypatch.setattr(
        QMessageBox, "warning",
        staticmethod(lambda *a, **k: warning_calls.append((a, k))))

    dlg._save()

    assert warning_calls, "不正なメールアドレスで警告が表示されていない"
    from app.services.member_service import get_members
    assert not any(m.member_number == "A-200" for m in get_members(db_session))


def test_save_accepts_valid_email_format(qtbot, db_session):
    from app.ui.dialogs.member_edit_dialog import MemberEditDialog
    dlg = MemberEditDialog(db_session, staff_name="担当者A")
    qtbot.addWidget(dlg)

    dlg._member_number.setText("A-201")
    dlg._org_name.setText("テスト商事2")
    dlg._name.setText("山田次郎")
    dlg._email_rows[0][0].setText("yamada@example.com")

    dlg._save()

    from app.services.member_service import get_members
    saved = next(m for m in get_members(db_session) if m.member_number == "A-201")
    assert saved.email_addresses[0].address == "yamada@example.com"
