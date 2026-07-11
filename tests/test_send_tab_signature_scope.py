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


def _patch_common(monkeypatch, staff=None, signatures=None):
    monkeypatch.setattr("app.ui.send_tab.get_session", lambda: _FakeSession())
    monkeypatch.setattr("app.ui.send_tab.get_positions", lambda s: [])
    monkeypatch.setattr("app.ui.send_tab.get_committees", lambda s: [])
    monkeypatch.setattr("app.ui.send_tab.get_members", lambda s: [])
    monkeypatch.setattr("app.ui.send_tab.get_templates", lambda s: [])
    monkeypatch.setattr("app.ui.send_tab.get_staff_by_name", lambda s, name: staff)
    monkeypatch.setattr("app.ui.send_tab.get_signatures", lambda s, sid: signatures or [])
    monkeypatch.setattr("app.ui.send_tab.get_default_signature", lambda s, sid: None)


def test_signature_combo_shows_only_own_signatures(qtbot, monkeypatch):
    staff = _Staff(3, "水谷")
    sigs = [_Signature(10, "水谷の署名")]
    _patch_common(monkeypatch, staff=staff, signatures=sigs)

    from app.ui.send_tab import SendTab
    tab = SendTab(staff_name="水谷")
    qtbot.addWidget(tab)

    labels = [tab._sig_combo.itemText(i) for i in range(tab._sig_combo.count())]
    assert "水谷の署名" in labels


def test_signature_combo_empty_when_staff_not_found(qtbot, monkeypatch):
    _patch_common(monkeypatch, staff=None, signatures=[])
    from app.ui.send_tab import SendTab
    tab = SendTab(staff_name="不明")
    qtbot.addWidget(tab)

    assert tab._sig_combo.count() == 1  # "（なし）"のみ
