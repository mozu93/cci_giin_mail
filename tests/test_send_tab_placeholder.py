from PyQt6.QtWidgets import QPushButton


class _FakeSession:
    def close(self):
        pass


def _patch_common(monkeypatch):
    monkeypatch.setattr("app.ui.send_tab.get_session", lambda: _FakeSession())
    monkeypatch.setattr("app.ui.send_tab.get_positions", lambda s: [])
    monkeypatch.setattr("app.ui.send_tab.get_committees", lambda s: [])
    monkeypatch.setattr("app.ui.send_tab.get_members", lambda s: [])
    monkeypatch.setattr("app.ui.send_tab.get_templates", lambda s: [])
    monkeypatch.setattr("app.ui.send_tab.get_signatures", lambda s: [])
    monkeypatch.setattr("app.ui.send_tab.get_default_signature", lambda s: None)
    monkeypatch.setattr("app.ui.send_tab.get_staff_by_name", lambda s, name: None)


def _placeholder_labels(tab):
    return [b.text() for b in tab.findChildren(QPushButton) if b.text().startswith("{")]


def test_placeholder_click_inserts_text_into_body(qtbot, monkeypatch):
    _patch_common(monkeypatch)
    from app.ui.send_tab import SendTab
    tab = SendTab(staff_name="担当者A")
    qtbot.addWidget(tab)

    tab._body_edit.clear()
    tab._insert_placeholder("{事業所名}")
    assert tab._body_edit.toPlainText() == "{事業所名}"


def test_merge_placeholders_hidden_without_dev_flag(qtbot, monkeypatch):
    monkeypatch.delenv("CCI_MAIL_DEV_TOOLS", raising=False)
    _patch_common(monkeypatch)
    from app.ui.send_tab import SendTab
    tab = SendTab(staff_name="担当者A")
    qtbot.addWidget(tab)

    labels = _placeholder_labels(tab)
    assert "{col1}" not in labels
    assert "{事業所名}" in labels


def test_merge_placeholders_shown_with_dev_flag(qtbot, monkeypatch):
    monkeypatch.setenv("CCI_MAIL_DEV_TOOLS", "1")
    _patch_common(monkeypatch)
    from app.ui.send_tab import SendTab
    tab = SendTab(staff_name="担当者A")
    qtbot.addWidget(tab)

    labels = _placeholder_labels(tab)
    assert "{col1}" in labels
