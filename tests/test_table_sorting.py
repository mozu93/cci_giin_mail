"""Tests for table sorting functionality."""
import pytest


class _FakeQuery:
    def order_by(self, *args):
        return self

    def all(self):
        return []


class _FakeSession:
    def query(self, *args):
        return _FakeQuery()

    def close(self):
        pass


def test_member_table_sorting_enabled(qtbot, monkeypatch):
    """Test that member table sorting is enabled after load."""
    monkeypatch.setattr("app.ui.member_tab.get_session", lambda: _FakeSession())
    monkeypatch.setattr("app.ui.member_tab.get_members", lambda *a, **k: [])

    from app.ui.member_tab import MemberTab
    tab = MemberTab()
    qtbot.addWidget(tab)
    assert tab._table.isSortingEnabled() is True


def test_history_job_table_sorting_enabled(qtbot, monkeypatch):
    """Test that history job table sorting is enabled after load."""
    monkeypatch.setattr("app.ui.history_tab.get_session", lambda: _FakeSession())
    monkeypatch.setattr("app.ui.history_tab.get_jobs", lambda s: [])

    from app.ui.history_tab import HistoryTab
    tab = HistoryTab()
    qtbot.addWidget(tab)
    assert tab._job_table.isSortingEnabled() is True
