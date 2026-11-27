from PyQt6.QtWidgets import QMessageBox


class _Member:
    def __init__(self, id):
        self.id = id
        self.member_number = f"A-{id:03d}"
        self.organization_name = f"org{id}"
        self.organization_kana = ""
        self.name = "テスト太郎"
        self.name_kana = ""
        self.title = ""
        self.position = None
        self.position_id = None
        self.committee_id = None
        self.committee_role = None
        self.display_order = None
        self.email_addresses = []


class _FakeSession:
    def close(self):
        pass


class _FakeDialog:
    def __init__(self, rows, members, parent=None):
        self._ids = {1, 3}

    def exec(self):
        return True

    def get_target_ids(self):
        return self._ids


def _make_tab(qtbot, monkeypatch):
    members = [_Member(1), _Member(2), _Member(3)]
    monkeypatch.setattr("app.ui.send_tab.get_session", lambda: _FakeSession())
    monkeypatch.setattr("app.ui.send_tab.get_positions", lambda s: [])
    monkeypatch.setattr("app.ui.send_tab.get_committees", lambda s: [])
    monkeypatch.setattr("app.ui.send_tab.get_members", lambda s: members)
    monkeypatch.setattr("app.ui.send_tab.get_templates", lambda s: [])
    monkeypatch.setattr("app.ui.send_tab.get_signatures", lambda s: [])
    monkeypatch.setattr("app.ui.send_tab.get_default_signature", lambda s: None)
    monkeypatch.setattr("app.ui.send_tab.get_staff_by_name", lambda s, name: None)
    from app.ui.send_tab import SendTab
    tab = SendTab(staff_name="担当者A")
    qtbot.addWidget(tab)
    return tab


def _patch_import(monkeypatch, answer):
    monkeypatch.setattr(
        "app.ui.send_tab.QFileDialog.getOpenFileName",
        lambda *a, **k: ("C:/tmp/list.csv", ""))
    monkeypatch.setattr(
        "app.services.import_service.load_member_file",
        lambda path: (["会員番号"], [["A-001"], ["A-003"]]))
    monkeypatch.setattr(
        "app.ui.dialogs.member_number_import_dialog.MemberNumberImportDialog",
        _FakeDialog)
    monkeypatch.setattr(
        "app.ui.send_tab.QMessageBox.question", lambda *a, **k: answer)


def test_member_number_mode_checks_and_restricts(qtbot, monkeypatch):
    tab = _make_tab(qtbot, monkeypatch)
    _patch_import(monkeypatch, QMessageBox.StandardButton.Yes)

    tab._rb_by_numbers.setChecked(True)
    assert not tab._numbers_panel.isHidden()
    tab._import_member_numbers()

    assert [m.id for m in tab._recipient.get_selected_members()] == [1, 3]
    table = tab._recipient._table
    visible = [r for r in range(table.rowCount()) if not table.isRowHidden(r)]
    assert len(visible) == 2


def test_member_number_mode_cancel_keeps_state(qtbot, monkeypatch):
    tab = _make_tab(qtbot, monkeypatch)
    _patch_import(monkeypatch, QMessageBox.StandardButton.No)

    tab._rb_by_numbers.setChecked(True)
    tab._import_member_numbers()

    assert tab._recipient.get_selected_members() == []
    assert tab._number_import_ids is None


def test_leaving_member_number_mode_clears_restriction(qtbot, monkeypatch):
    tab = _make_tab(qtbot, monkeypatch)
    _patch_import(monkeypatch, QMessageBox.StandardButton.Yes)

    tab._rb_by_numbers.setChecked(True)
    tab._import_member_numbers()
    tab._rb_by_list.setChecked(True)

    table = tab._recipient._table
    assert all(not table.isRowHidden(r) for r in range(table.rowCount()))
    assert tab._number_import_ids is None
