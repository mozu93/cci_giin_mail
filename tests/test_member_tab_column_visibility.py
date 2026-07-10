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


def test_toggling_column_off_hides_it_and_persists(qtbot, monkeypatch):
    saved = {}
    monkeypatch.setattr("app.ui.member_tab.get_session", lambda: _FakeSession())
    monkeypatch.setattr("app.ui.member_tab.get_members", lambda *a, **k: [])
    monkeypatch.setattr(
        "app.services.settings_service.get_hidden_columns", lambda key: [])
    monkeypatch.setattr(
        "app.services.settings_service.set_hidden_columns",
        lambda key, hidden: saved.__setitem__(key, hidden))

    from app.ui.member_tab import MemberTab
    tab = MemberTab()
    qtbot.addWidget(tab)

    assert tab._table.isColumnHidden(3) is False  # 委員会列

    tab._toggle_column(3, visible=False)

    assert tab._table.isColumnHidden(3) is True
    assert saved["member_tab"] == [3]


def test_toggling_column_back_on_shows_it_again(qtbot, monkeypatch):
    saved = {}
    monkeypatch.setattr("app.ui.member_tab.get_session", lambda: _FakeSession())
    monkeypatch.setattr("app.ui.member_tab.get_members", lambda *a, **k: [])
    monkeypatch.setattr(
        "app.services.settings_service.get_hidden_columns", lambda key: [])
    monkeypatch.setattr(
        "app.services.settings_service.set_hidden_columns",
        lambda key, hidden: saved.__setitem__(key, hidden))

    from app.ui.member_tab import MemberTab
    tab = MemberTab()
    qtbot.addWidget(tab)

    tab._toggle_column(3, visible=False)
    tab._toggle_column(3, visible=True)

    assert tab._table.isColumnHidden(3) is False
    assert saved["member_tab"] == []


def test_hidden_columns_restored_on_load(qtbot, monkeypatch):
    monkeypatch.setattr("app.ui.member_tab.get_session", lambda: _FakeSession())
    monkeypatch.setattr("app.ui.member_tab.get_members", lambda *a, **k: [])
    monkeypatch.setattr(
        "app.services.settings_service.get_hidden_columns",
        lambda key: [3, 5] if key == "member_tab" else [])

    from app.ui.member_tab import MemberTab
    tab = MemberTab()
    qtbot.addWidget(tab)

    assert tab._table.isColumnHidden(3) is True
    assert tab._table.isColumnHidden(5) is True
    assert tab._table.isColumnHidden(4) is False
