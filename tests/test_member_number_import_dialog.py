from app.services.member_service import create_member, get_members


def _setup(db_session, monkeypatch):
    monkeypatch.setattr(
        "app.ui.dialogs.member_number_import_dialog.get_session",
        lambda: db_session)
    a = create_member(db_session, "A-001", "○○商事", "山田太郎")
    b = create_member(db_session, "A-002", "△△産業", "鈴木花子")
    c = create_member(db_session, "A-003", "□□工業", "佐藤次郎")
    return a, b, c, get_members(db_session)


def test_dialog_matched_mode_selects_listed_members(qtbot, db_session, monkeypatch):
    from app.ui.dialogs.member_number_import_dialog import MemberNumberImportDialog
    a, b, c, members = _setup(db_session, monkeypatch)
    rows = [["会員番号"], ["A-001"], ["A-003"], ["X-999"]]
    dlg = MemberNumberImportDialog(rows, members)
    qtbot.addWidget(dlg)

    assert dlg.get_target_ids() == {a.id, c.id}
    assert "X-999" in dlg._detail.toPlainText()


def test_dialog_unmatched_mode_selects_members_not_listed(
        qtbot, db_session, monkeypatch):
    from app.ui.dialogs.member_number_import_dialog import MemberNumberImportDialog
    a, b, c, members = _setup(db_session, monkeypatch)
    rows = [["会員番号"], ["A-001"], ["A-003"]]
    dlg = MemberNumberImportDialog(rows, members)
    qtbot.addWidget(dlg)

    dlg._rb_unmatched.setChecked(True)
    assert dlg.get_target_ids() == {b.id}


def test_dialog_headerless_file_uses_first_row_as_data(
        qtbot, db_session, monkeypatch):
    from app.ui.dialogs.member_number_import_dialog import MemberNumberImportDialog
    a, b, c, members = _setup(db_session, monkeypatch)
    rows = [["A-001"], ["A-002"]]
    dlg = MemberNumberImportDialog(rows, members)
    qtbot.addWidget(dlg)

    dlg._chk_header.setChecked(False)
    assert dlg.get_target_ids() == {a.id, b.id}


def test_dialog_disables_ok_when_nothing_selected(qtbot, db_session, monkeypatch):
    from app.ui.dialogs.member_number_import_dialog import MemberNumberImportDialog
    a, b, c, members = _setup(db_session, monkeypatch)
    dlg = MemberNumberImportDialog([["会員番号"], ["X-999"]], members)
    qtbot.addWidget(dlg)

    assert dlg.get_target_ids() == set()
    assert not dlg._btn_ok.isEnabled()
