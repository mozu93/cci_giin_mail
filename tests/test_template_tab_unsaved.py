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


def test_delete_dirty_template_does_not_show_second_discard_prompt(qtbot, monkeypatch):
    """削除確認ダイアログの後に、未保存変更の破棄確認が二重表示されないことを確認する。

    _delete() は _current_id を選択中のテンプレートの削除で確定させるため、
    ユーザーが既に「削除確認」で同意した後に _new() 経由の
    _confirm_discard() を再度表示してはならない。
    """
    templates = [_FakeTemplate(1, "テンプレA", "件名A", "本文A")]

    monkeypatch.setattr(
        "app.ui.template_tab.get_session", lambda: _FakeSession())
    monkeypatch.setattr(
        "app.ui.template_tab.get_templates", lambda s: list(templates))
    monkeypatch.setattr("app.ui.template_tab.get_signatures", lambda s: [])

    deleted_ids = []

    def _fake_delete_template(session, template_id):
        deleted_ids.append(template_id)
        templates.clear()

    monkeypatch.setattr(
        "app.ui.template_tab.delete_template", _fake_delete_template)

    from app.ui.template_tab import TemplateTab
    tab = TemplateTab()
    qtbot.addWidget(tab)

    tab._list.setCurrentRow(0)
    assert tab._current_id == 1

    tab._name.setText("編集後の名前")  # 保存前に編集し、未保存状態を作る
    assert tab._is_dirty() is True

    calls = []

    def _fake_question(*args, **kwargs):
        calls.append(args)
        return QMessageBox.StandardButton.Yes

    monkeypatch.setattr(QMessageBox, "question", staticmethod(_fake_question))

    tab._delete()

    assert deleted_ids == [1]
    assert len(calls) == 1, "削除確認以外のダイアログ（二重の未保存確認）が表示された"
    assert tab._current_id is None
    assert tab._name.text() == ""
    assert tab._subject.text() == ""
    assert tab._body.toPlainText() == ""
    assert tab._is_dirty() is False


def test_on_select_reverts_selection_when_discard_declined(qtbot, monkeypatch):
    templates = [
        _FakeTemplate(1, "テンプレA", "件名A", "本文A"),
        _FakeTemplate(2, "テンプレB", "件名B", "本文B"),
    ]
    monkeypatch.setattr(
        "app.ui.template_tab.get_session", lambda: _FakeSession())
    monkeypatch.setattr(
        "app.ui.template_tab.get_templates", lambda s: list(templates))
    monkeypatch.setattr("app.ui.template_tab.get_signatures", lambda s: [])

    from app.ui.template_tab import TemplateTab
    tab = TemplateTab()
    qtbot.addWidget(tab)

    tab._list.setCurrentRow(0)
    assert tab._current_id == 1

    tab._name.setText("編集後")  # 未保存の変更を作る
    monkeypatch.setattr(
        QMessageBox, "question",
        staticmethod(lambda *a, **k: QMessageBox.StandardButton.No))

    tab._list.setCurrentRow(1)

    assert tab._current_id == 1, "破棄が拒否されたのに選択が切り替わった"
    assert tab._list.currentRow() == 0, "選択行が元に戻っていない"
    assert tab._name.text() == "編集後", "フォームの内容が失われた"


def test_save_clears_dirty_flag(qtbot, monkeypatch):
    monkeypatch.setattr(
        "app.ui.template_tab.get_session", lambda: _FakeSession())
    monkeypatch.setattr("app.ui.template_tab.get_templates", lambda s: [])
    monkeypatch.setattr("app.ui.template_tab.get_signatures", lambda s: [])
    monkeypatch.setattr(
        "app.ui.template_tab.create_template",
        lambda s, name, subject, body, signature_id=None: None)
    monkeypatch.setattr(
        QMessageBox, "information", staticmethod(lambda *a, **k: None))

    from app.ui.template_tab import TemplateTab
    tab = TemplateTab()
    qtbot.addWidget(tab)

    tab._name.setText("新規テンプレ")
    tab._subject.setText("新規件名")
    assert tab._is_dirty() is True

    tab._save()

    assert tab._is_dirty() is False


class _FakeSession:
    def close(self):
        pass


class _FakeTemplate:
    def __init__(self, id, name, subject, body, signature_id=None):
        self.id = id
        self.name = name
        self.subject = subject
        self.body = body
        self.signature_id = signature_id
