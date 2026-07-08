"""Test empty-state guidance display for member and template tabs."""
import pytest


class _FakeSession:
    def close(self):
        pass


def test_member_tab_shows_guidance_when_empty(qtbot, monkeypatch):
    """Member tab should display guidance text when the member list is empty."""
    monkeypatch.setattr("app.ui.member_tab.get_session", lambda: _FakeSession())
    monkeypatch.setattr("app.ui.member_tab.get_members", lambda *a, **k: [])
    monkeypatch.setattr("app.ui.member_tab.MemberTab._load_positions", lambda self: None)

    from app.ui.member_tab import MemberTab
    tab = MemberTab()
    qtbot.addWidget(tab)
    assert hasattr(tab, '_empty_hint'), "MemberTab should have _empty_hint attribute"
    assert tab._empty_hint.isVisible() is True


def test_member_tab_hides_guidance_with_filter(qtbot, monkeypatch):
    """Member tab should hide guidance text even if list is empty when a filter is active."""
    monkeypatch.setattr("app.ui.member_tab.get_session", lambda: _FakeSession())
    monkeypatch.setattr("app.ui.member_tab.get_members", lambda *a, **k: [])
    monkeypatch.setattr("app.ui.member_tab.MemberTab._load_positions", lambda self: None)

    from app.ui.member_tab import MemberTab
    tab = MemberTab()
    qtbot.addWidget(tab)

    # Apply search filter
    tab._search.setText("test")
    assert tab._empty_hint.isVisible() is False


def test_template_tab_shows_guidance_when_empty(qtbot, monkeypatch):
    """Template tab should display guidance text when the template list is empty."""
    monkeypatch.setattr("app.ui.template_tab.get_session", lambda: _FakeSession())
    monkeypatch.setattr("app.ui.template_tab.get_templates", lambda s: [])
    monkeypatch.setattr("app.ui.template_tab.get_signatures", lambda s: [])

    from app.ui.template_tab import TemplateTab
    tab = TemplateTab()
    qtbot.addWidget(tab)
    assert hasattr(tab, '_empty_hint'), "TemplateTab should have _empty_hint attribute"
    assert tab._empty_hint.isVisible() is True


def test_template_tab_hides_guidance_when_not_empty(qtbot, monkeypatch):
    """Template tab should hide guidance text when the template list has items."""
    # Create a mock template object with all required attributes
    class MockTemplate:
        def __init__(self):
            self.id = 1
            self.name = "Test Template"
            self.subject = "Test Subject"
            self.body = "Test Body"
            self.signature_id = None

    monkeypatch.setattr("app.ui.template_tab.get_session", lambda: _FakeSession())
    monkeypatch.setattr("app.ui.template_tab.get_templates", lambda s: [MockTemplate()])
    monkeypatch.setattr("app.ui.template_tab.get_signatures", lambda s: [])

    from app.ui.template_tab import TemplateTab
    tab = TemplateTab()
    qtbot.addWidget(tab)
    assert tab._empty_hint.isVisible() is False
