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
    monkeypatch.setattr("app.services.meeting_service.get_meetings", lambda s: [])


def test_list_mode_is_default_and_hides_filter_panels(qtbot, monkeypatch):
    _patch_common(monkeypatch)
    from app.ui.send_tab import SendTab
    tab = SendTab(staff_name="担当者A")
    qtbot.addWidget(tab)
    tab.show()

    assert tab._rb_by_list.isChecked() is True
    assert tab._pos_panel.isVisible() is False
    assert tab._committee_panel.isVisible() is False
    assert tab._attend_panel.isVisible() is False


def test_switching_to_pos_mode_shows_pos_panel_then_back_to_list_hides_it(qtbot, monkeypatch):
    _patch_common(monkeypatch)
    from app.ui.send_tab import SendTab
    tab = SendTab(staff_name="担当者A")
    qtbot.addWidget(tab)
    tab.show()

    tab._rb_by_pos.setChecked(True)
    assert tab._pos_panel.isVisible() is True

    tab._rb_by_list.setChecked(True)
    assert tab._pos_panel.isVisible() is False


def test_switching_from_attend_directly_to_list_hides_attend_panel(qtbot, monkeypatch):
    _patch_common(monkeypatch)
    from app.ui.send_tab import SendTab
    tab = SendTab(staff_name="担当者A")
    qtbot.addWidget(tab)
    tab.show()

    tab._rb_by_attend.setChecked(True)
    assert tab._attend_panel.isVisible() is True

    tab._rb_by_list.setChecked(True)
    assert tab._attend_panel.isVisible() is False


def test_clear_all_resets_to_list_mode(qtbot, monkeypatch):
    _patch_common(monkeypatch)
    from app.ui.send_tab import SendTab
    tab = SendTab(staff_name="担当者A")
    qtbot.addWidget(tab)

    tab._rb_by_pos.setChecked(True)
    tab._clear_all()
    assert tab._rb_by_list.isChecked() is True
