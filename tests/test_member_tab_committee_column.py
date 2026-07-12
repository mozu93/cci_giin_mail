def test_member_tab_shows_committee_column(qtbot, monkeypatch):
    class _Committee:
        name = "総務・運営委員会"

    class _Member:
        def __init__(self):
            self.id = 1
            self.member_number = "A-001"
            self.organization_name = "テスト商事"
            self.organization_kana = ""
            self.name = "山田太郎"
            self.name_kana = ""
            self.title = ""
            self.position = None
            self.committee = _Committee()
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

    monkeypatch.setattr("app.ui.member_tab.get_session", lambda: _FakeSession())
    monkeypatch.setattr("app.ui.member_tab.get_members", lambda *a, **k: [_Member()])

    from app.ui.member_tab import MemberTab
    tab = MemberTab()
    qtbot.addWidget(tab)

    assert tab._table.columnCount() == 11
    assert tab._table.horizontalHeaderItem(3).text() == "委員会"
    assert tab._table.item(0, 3).text() == "総務・運営委員会"
