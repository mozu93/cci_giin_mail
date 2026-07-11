class _FakeSession:
    def close(self):
        pass


class _Staff:
    def __init__(self, id, name):
        self.id = id
        self.name = name


class _Signature:
    def __init__(self, id, name):
        self.id = id
        self.name = name


def test_template_tab_signature_combo_scoped_to_staff(qtbot, monkeypatch):
    staff = _Staff(4, "山田")
    sigs = [_Signature(20, "山田の署名")]
    monkeypatch.setattr("app.ui.template_tab.get_session", lambda: _FakeSession())
    monkeypatch.setattr("app.ui.template_tab.get_templates", lambda s: [])
    monkeypatch.setattr("app.ui.template_tab.get_staff_by_name", lambda s, name: staff)
    monkeypatch.setattr(
        "app.ui.template_tab.get_signatures",
        lambda s, sid: sigs if sid == 4 else [])

    from app.ui.template_tab import TemplateTab
    tab = TemplateTab(staff_name="山田")
    qtbot.addWidget(tab)

    labels = [tab._sig_combo.itemText(i) for i in range(tab._sig_combo.count())]
    assert "山田の署名" in labels


def test_template_tab_without_staff_name_shows_no_signatures(qtbot, monkeypatch):
    monkeypatch.setattr("app.ui.template_tab.get_session", lambda: _FakeSession())
    monkeypatch.setattr("app.ui.template_tab.get_templates", lambda s: [])
    monkeypatch.setattr("app.ui.template_tab.get_staff_by_name", lambda s, name: None)

    def fail_if_called(session, staff_id):
        raise AssertionError("staff_id が None のときは get_signatures を呼ばないこと")

    monkeypatch.setattr("app.ui.template_tab.get_signatures", fail_if_called)

    from app.ui.template_tab import TemplateTab
    tab = TemplateTab()
    qtbot.addWidget(tab)

    assert tab._sig_combo.count() == 1
