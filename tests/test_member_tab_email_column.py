# tests/test_member_tab_email_column.py
def test_table_has_10_columns_with_single_email_column(qtbot, monkeypatch):
    monkeypatch.setattr("app.ui.member_tab.get_session", lambda: _FakeSession())
    monkeypatch.setattr("app.ui.member_tab.get_members", lambda *a, **k: [_Member()])

    from app.ui.member_tab import MemberTab
    tab = MemberTab()
    qtbot.addWidget(tab)

    headers = [tab._table.horizontalHeaderItem(i).text()
               for i in range(tab._table.columnCount())]
    assert tab._table.columnCount() == 11
    assert "メール(件数)" in headers
    email_col = headers.index("メール(件数)")
    assert tab._table.item(0, email_col).text() == "2件"


class _Email:
    def __init__(self, address, label=""):
        self.address = address
        self.label = label


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
        self.committee = None
        self.email_addresses = [_Email("a@example.com"), _Email("b@example.com")]
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
