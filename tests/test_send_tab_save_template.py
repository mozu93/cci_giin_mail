from PyQt6.QtWidgets import QInputDialog, QMessageBox


class _FakeSession:
    def close(self):
        pass

    def get(self, *args, **kwargs):
        return None


class _Template:
    def __init__(self, id, name, subject="", body="", signature_id=None):
        self.id = id
        self.name = name
        self.subject = subject
        self.body = body
        self.signature_id = signature_id


def _patch_common(monkeypatch, templates=None):
    monkeypatch.setattr("app.ui.send_tab.get_session", lambda: _FakeSession())
    monkeypatch.setattr("app.ui.send_tab.get_positions", lambda s: [])
    monkeypatch.setattr("app.ui.send_tab.get_committees", lambda s: [])
    monkeypatch.setattr("app.ui.send_tab.get_members", lambda s: [])
    monkeypatch.setattr("app.ui.send_tab.get_templates", lambda s: templates or [])
    monkeypatch.setattr("app.ui.send_tab.get_signatures", lambda s: [])
    monkeypatch.setattr("app.ui.send_tab.get_default_signature", lambda s: None)


def test_save_as_template_creates_new_when_none_selected(qtbot, monkeypatch):
    _patch_common(monkeypatch)
    created = {}

    def fake_create_template(session, name, subject, body, signature_id=None):
        created["args"] = (name, subject, body, signature_id)
        return _Template(99, name, subject, body, signature_id)

    monkeypatch.setattr("app.ui.send_tab.create_template", fake_create_template)
    monkeypatch.setattr(QInputDialog, "getText",
                        staticmethod(lambda *a, **k: ("新テンプレ", True)))

    from app.ui.send_tab import SendTab
    tab = SendTab(staff_name="担当者A")
    qtbot.addWidget(tab)
    tab._subject_edit.setText("件名A")
    tab._body_edit.setPlainText("本文A")

    tab._save_as_template()

    assert created["args"] == ("新テンプレ", "件名A", "本文A", None)


def test_save_as_template_overwrites_when_selected(qtbot, monkeypatch):
    tmpl = _Template(5, "既存テンプレ", "旧件名", "旧本文")
    _patch_common(monkeypatch, templates=[tmpl])
    updated = {}

    def fake_update_template(session, template_id, **kwargs):
        updated["args"] = (template_id, kwargs)
        return tmpl

    monkeypatch.setattr("app.ui.send_tab.update_template", fake_update_template)
    monkeypatch.setattr(QMessageBox, "question",
                        staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes))

    from app.ui.send_tab import SendTab
    tab = SendTab(staff_name="担当者A")
    qtbot.addWidget(tab)
    for i in range(tab._template_combo.count()):
        if tab._template_combo.itemData(i) == 5:
            tab._template_combo.setCurrentIndex(i)
            break
    tab._subject_edit.setText("新件名")
    tab._body_edit.setPlainText("新本文")

    tab._save_as_template()

    assert updated["args"][0] == 5
    assert updated["args"][1]["subject"] == "新件名"
    assert updated["args"][1]["body"] == "新本文"


def test_save_as_template_shows_error_on_create_failure(qtbot, monkeypatch):
    _patch_common(monkeypatch)

    def fake_create_template(session, name, subject, body, signature_id=None):
        raise RuntimeError("DB書き込みエラー")

    monkeypatch.setattr("app.ui.send_tab.create_template", fake_create_template)
    monkeypatch.setattr(QInputDialog, "getText",
                        staticmethod(lambda *a, **k: ("新テンプレ", True)))

    errors = []
    monkeypatch.setattr(QMessageBox, "critical",
                        staticmethod(lambda *a, **k: errors.append(a)))

    from app.ui.send_tab import SendTab
    tab = SendTab(staff_name="担当者A")
    qtbot.addWidget(tab)
    tab._subject_edit.setText("件名A")
    tab._body_edit.setPlainText("本文A")

    tab._save_as_template()  # 例外が伝播せず、エラーダイアログが出ること

    assert errors, "create_template失敗時はQMessageBox.criticalを表示すること"


def test_save_as_template_shows_error_on_update_failure(qtbot, monkeypatch):
    tmpl = _Template(5, "既存テンプレ", "旧件名", "旧本文")
    _patch_common(monkeypatch, templates=[tmpl])

    def fake_update_template(session, template_id, **kwargs):
        raise RuntimeError("DB書き込みエラー")

    monkeypatch.setattr("app.ui.send_tab.update_template", fake_update_template)
    monkeypatch.setattr(QMessageBox, "question",
                        staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes))

    errors = []
    monkeypatch.setattr(QMessageBox, "critical",
                        staticmethod(lambda *a, **k: errors.append(a)))

    from app.ui.send_tab import SendTab
    tab = SendTab(staff_name="担当者A")
    qtbot.addWidget(tab)
    for i in range(tab._template_combo.count()):
        if tab._template_combo.itemData(i) == 5:
            tab._template_combo.setCurrentIndex(i)
            break
    tab._subject_edit.setText("新件名")
    tab._body_edit.setPlainText("新本文")

    tab._save_as_template()  # 例外が伝播せず、エラーダイアログが出ること

    assert errors, "update_template失敗時はQMessageBox.criticalを表示すること"


def test_save_as_template_requires_subject_and_body(qtbot, monkeypatch):
    _patch_common(monkeypatch)

    from app.ui.send_tab import SendTab
    tab = SendTab(staff_name="担当者A")
    qtbot.addWidget(tab)
    tab._subject_edit.clear()
    tab._body_edit.clear()

    warned = []
    monkeypatch.setattr(QMessageBox, "warning",
                        staticmethod(lambda *a, **k: warned.append(True)))

    tab._save_as_template()
    assert warned, "件名・本文が空の場合は警告を表示すること"
