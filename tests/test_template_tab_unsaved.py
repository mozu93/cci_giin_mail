import pytest
from PyQt6.QtWidgets import QMessageBox


def test_selecting_other_template_prompts_when_dirty(qtbot, monkeypatch):
    monkeypatch.setattr(
        "app.ui.template_tab.get_session", lambda: _FakeSession())
    monkeypatch.setattr("app.ui.template_tab.get_templates", lambda s: [])
    monkeypatch.setattr("app.ui.template_tab.get_signatures", lambda s: [])

    from app.ui.template_tab import TemplateTab
    tab = TemplateTab()
    qtbot.addWidget(tab)

    tab._name.setText("新しい名前")  # 未保存の変更を作る
    assert tab._is_dirty() is True

    calls = []
    monkeypatch.setattr(
        QMessageBox, "question",
        staticmethod(lambda *a, **k: (calls.append((a, k)),
                                       QMessageBox.StandardButton.No)[1]))
    assert tab._confirm_discard() is False
    assert calls, "未保存確認ダイアログが表示されていない"


class _FakeSession:
    def close(self):
        pass
