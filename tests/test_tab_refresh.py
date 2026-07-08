import pytest


def test_history_tab_has_refresh(qtbot, monkeypatch):
    monkeypatch.setattr("app.ui.history_tab.get_session", lambda: _FakeSession())
    monkeypatch.setattr("app.ui.history_tab.get_jobs", lambda s: [])

    from app.ui.history_tab import HistoryTab
    tab = HistoryTab()
    qtbot.addWidget(tab)
    assert hasattr(tab, "refresh")
    tab.refresh()  # 例外なく再読込できること


def test_member_tab_has_refresh(qtbot, monkeypatch):
    monkeypatch.setattr("app.ui.member_tab.get_session", lambda: _FakeSession())
    monkeypatch.setattr("app.ui.member_tab.get_members", lambda *a, **k: [])

    from app.ui.member_tab import MemberTab
    tab = MemberTab()
    qtbot.addWidget(tab)
    assert hasattr(tab, "refresh")
    tab.refresh()


class _FakeQuery:
    def __init__(self, result):
        self.result = result

    def order_by(self, *args):
        return self

    def all(self):
        return self.result


class _FakeSession:
    def query(self, model):
        return _FakeQuery([])

    def close(self):
        pass
