import pytest


def test_edit_buttons_disabled_until_row_selected(qtbot, monkeypatch):
    fake_session = _FakeSession()
    monkeypatch.setattr("app.ui.member_tab.get_session", lambda: fake_session)
    monkeypatch.setattr("app.ui.member_tab.get_members", lambda *a, **k: [_Member()])

    from app.ui.member_tab import MemberTab
    tab = MemberTab()
    qtbot.addWidget(tab)

    assert tab._btn_edit.isEnabled() is False
    assert tab._btn_history.isEnabled() is False
    assert tab._btn_retire.isEnabled() is False

    tab._table.selectRow(0)
    assert tab._btn_edit.isEnabled() is True
    assert tab._btn_history.isEnabled() is True
    assert tab._btn_retire.isEnabled() is True


def test_buttons_redisable_after_refresh_empty_list(qtbot, monkeypatch):
    fake_session = _FakeSession()
    monkeypatch.setattr("app.ui.member_tab.get_session", lambda: fake_session)
    monkeypatch.setattr("app.ui.member_tab.get_members", lambda *a, **k: [_Member()])

    from app.ui.member_tab import MemberTab
    tab = MemberTab()
    qtbot.addWidget(tab)

    # Buttons start disabled
    assert tab._btn_edit.isEnabled() is False
    assert tab._btn_history.isEnabled() is False
    assert tab._btn_retire.isEnabled() is False

    # Select row; buttons become enabled
    tab._table.selectRow(0)
    assert tab._btn_edit.isEnabled() is True
    assert tab._btn_history.isEnabled() is True
    assert tab._btn_retire.isEnabled() is True

    # Re-monkeypatch get_members to return empty list
    monkeypatch.setattr("app.ui.member_tab.get_members", lambda *a, **k: [])

    # Call refresh() which calls _load(), which clears table and calls _on_selection_changed()
    tab.refresh()

    # Buttons should be re-disabled because table is now empty
    assert tab._btn_edit.isEnabled() is False
    assert tab._btn_history.isEnabled() is False
    assert tab._btn_retire.isEnabled() is False


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
