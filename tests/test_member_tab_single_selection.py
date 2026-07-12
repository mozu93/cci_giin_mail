from PyQt6.QtWidgets import QTableWidget


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
        self.committee = None
        self.email_addresses = []
        self.is_active = True
        self.updated_at = None
        self.photo_thumb = None
        self.display_order = None


class _FakeQuery:
    def __init__(self, items=None):
        self.items = items or []

    def order_by(self, *args):
        return self

    def all(self):
        return self.items


class _FakeSession:
    def close(self):
        pass

    def query(self, model):
        return _FakeQuery([])


def test_table_selection_mode_is_single(qtbot, monkeypatch):
    members = [_Member(1), _Member(2), _Member(3)]
    monkeypatch.setattr("app.ui.member_tab.get_session", lambda: _FakeSession())
    monkeypatch.setattr("app.ui.member_tab.get_members", lambda *a, **k: members)

    from app.ui.member_tab import MemberTab
    tab = MemberTab()
    qtbot.addWidget(tab)

    assert tab._table.selectionMode() == QTableWidget.SelectionMode.SingleSelection
