# tests/test_member_edit_dialog_unsaved.py
import pytest
from PyQt6.QtWidgets import QDialog, QMessageBox


def test_reject_prompts_when_dirty(qtbot, db_session, monkeypatch):
    from app.ui.dialogs.member_edit_dialog import MemberEditDialog
    dlg = MemberEditDialog(db_session, staff_name="担当者A")
    qtbot.addWidget(dlg)

    dlg._org_name.setText("テスト事業所")  # 未保存の変更を作る
    assert dlg._is_dirty() is True

    question_calls = []
    monkeypatch.setattr(
        QMessageBox, "question",
        staticmethod(lambda *a, **k: (question_calls.append((a, k)),
                                       QMessageBox.StandardButton.No)[1]))
    super_reject_calls = []
    monkeypatch.setattr(QDialog, "reject", lambda self: super_reject_calls.append(True))

    dlg.reject()
    assert question_calls, "未保存確認ダイアログが表示されていない"
    assert super_reject_calls == [], "破棄しないと回答した場合はダイアログを閉じてはならない"
