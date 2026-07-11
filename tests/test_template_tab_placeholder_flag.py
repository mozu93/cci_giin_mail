from PyQt6.QtWidgets import QPushButton


class _FakeSession:
    def close(self):
        pass


def _placeholder_labels(tab):
    return [b.text() for b in tab.findChildren(QPushButton) if b.text().startswith("{")]


def test_merge_placeholders_hidden_without_dev_flag(qtbot, monkeypatch):
    monkeypatch.delenv("CCI_MAIL_DEV_TOOLS", raising=False)
    monkeypatch.setattr("app.ui.template_tab.get_session", lambda: _FakeSession())
    monkeypatch.setattr("app.ui.template_tab.get_templates", lambda s: [])
    monkeypatch.setattr("app.ui.template_tab.get_signatures", lambda s: [])

    from app.ui.template_tab import TemplateTab
    tab = TemplateTab()
    qtbot.addWidget(tab)

    labels = _placeholder_labels(tab)
    assert "{col1}" not in labels
    assert "{事業所名}" in labels


def test_merge_placeholders_shown_with_dev_flag(qtbot, monkeypatch):
    monkeypatch.setenv("CCI_MAIL_DEV_TOOLS", "1")
    monkeypatch.setattr("app.ui.template_tab.get_session", lambda: _FakeSession())
    monkeypatch.setattr("app.ui.template_tab.get_templates", lambda s: [])
    monkeypatch.setattr("app.ui.template_tab.get_signatures", lambda s: [])

    from app.ui.template_tab import TemplateTab
    tab = TemplateTab()
    qtbot.addWidget(tab)

    labels = _placeholder_labels(tab)
    assert "{col1}" in labels
