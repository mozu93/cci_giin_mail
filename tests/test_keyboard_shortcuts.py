from unittest.mock import Mock
from PyQt6.QtGui import QKeySequence


def test_template_tab_ctrl_s_triggers_save(qtbot, monkeypatch):
    monkeypatch.setattr("app.ui.template_tab.get_session", lambda: _FakeSession())
    monkeypatch.setattr("app.ui.template_tab.get_templates", lambda s: [])
    monkeypatch.setattr("app.ui.template_tab.get_signatures", lambda s: [])

    from app.ui.template_tab import TemplateTab
    tab = TemplateTab()
    qtbot.addWidget(tab)

    called = []
    tab._save = lambda: called.append(True)
    shortcuts = [sc for sc in tab.findChildren(__import__(
        "PyQt6.QtGui", fromlist=["QShortcut"]).QShortcut)
        if sc.key() == QKeySequence("Ctrl+S")]
    assert shortcuts, "Ctrl+S ショートカットが登録されていない"


def test_member_tab_ctrl_f_focuses_search(qtbot, monkeypatch):
    monkeypatch.setattr("app.ui.member_tab.get_session", lambda: _FakeSession())
    monkeypatch.setattr("app.ui.member_tab.get_members", lambda *a, **k: [])

    from app.ui.member_tab import MemberTab
    tab = MemberTab()
    qtbot.addWidget(tab)
    shortcuts = [sc for sc in tab.findChildren(__import__(
        "PyQt6.QtGui", fromlist=["QShortcut"]).QShortcut)
        if sc.key() == QKeySequence("Ctrl+F")]
    assert shortcuts, "Ctrl+F ショートカットが登録されていない"


class _FakeSession:
    def __init__(self):
        self.query_mock = Mock(return_value=Mock(order_by=Mock(return_value=Mock(all=Mock(return_value=[])))))

    def close(self):
        pass

    def query(self, *args, **kwargs):
        return self.query_mock.return_value
