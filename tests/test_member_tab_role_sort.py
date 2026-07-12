from PyQt6.QtCore import Qt


class _Position:
    def __init__(self, name, sort_order):
        self.name = name
        self.sort_order = sort_order


class _Member:
    def __init__(self, id, position, organization_kana, member_number="A-001",
                 display_order=None):
        self.id = id
        self.member_number = member_number
        self.organization_name = f"org{id}"
        self.organization_kana = organization_kana
        self.name = "テスト太郎"
        self.name_kana = ""
        self.title = ""
        self.position = position
        self.committee = None
        self.email_addresses = []
        self.is_active = True
        self.updated_at = None
        self.photo_thumb = None
        self.display_order = display_order


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


def test_role_column_sorts_by_position_order_then_kana(qtbot, monkeypatch):
    kaicho = _Position("会頭", 1)
    giin = _Position("議員", 5)

    # 順番設定順・フリガナ順とは無関係な順序でロードし、ソートで正しい順序になることを確認する
    members = [
        _Member(1, giin, "ハナコ"),
        _Member(2, kaicho, "タロウ"),
        _Member(3, giin, "アイコ"),
    ]

    monkeypatch.setattr("app.ui.member_tab.get_session", lambda: _FakeSession())
    monkeypatch.setattr("app.ui.member_tab.get_members", lambda *a, **k: members)

    from app.ui.member_tab import MemberTab
    tab = MemberTab()
    qtbot.addWidget(tab)

    tab._table.sortItems(2, Qt.SortOrder.AscendingOrder)

    org_names_in_order = [
        tab._table.item(r, 4).text() for r in range(tab._table.rowCount())
    ]
    # 会頭(sort_order=1)のorg2が先頭、続いて議員(sort_order=5)内はフリガナ順(アイコ→ハナコ)
    assert org_names_in_order == ["org2", "org3", "org1"]


def test_role_column_sorts_vice_chairs_by_display_order_not_kana(qtbot, monkeypatch):
    fukukaicho = _Position("副会頭", 2)

    # フリガナ順なら アイコ→サブロウ→ハナコ (org2, org3, org1) だが、
    # 就任順設定(display_order)ではハナコ→アイコ→サブロウ (org1, org2, org3) の想定
    members = [
        _Member(1, fukukaicho, "ハナコ", display_order=1),
        _Member(2, fukukaicho, "アイコ", display_order=2),
        _Member(3, fukukaicho, "サブロウ", display_order=3),
    ]

    monkeypatch.setattr("app.ui.member_tab.get_session", lambda: _FakeSession())
    monkeypatch.setattr("app.ui.member_tab.get_members", lambda *a, **k: members)

    from app.ui.member_tab import MemberTab
    tab = MemberTab()
    qtbot.addWidget(tab)

    tab._table.sortItems(2, Qt.SortOrder.AscendingOrder)

    org_names_in_order = [
        tab._table.item(r, 4).text() for r in range(tab._table.rowCount())
    ]
    assert org_names_in_order == ["org1", "org2", "org3"]


def test_role_column_places_no_position_members_last(qtbot, monkeypatch):
    kaicho = _Position("会頭", 1)
    members = [
        _Member(1, None, "アイコ"),
        _Member(2, kaicho, "タロウ"),
    ]

    monkeypatch.setattr("app.ui.member_tab.get_session", lambda: _FakeSession())
    monkeypatch.setattr("app.ui.member_tab.get_members", lambda *a, **k: members)

    from app.ui.member_tab import MemberTab
    tab = MemberTab()
    qtbot.addWidget(tab)

    tab._table.sortItems(2, Qt.SortOrder.AscendingOrder)

    org_names_in_order = [
        tab._table.item(r, 4).text() for r in range(tab._table.rowCount())
    ]
    assert org_names_in_order == ["org2", "org1"]
