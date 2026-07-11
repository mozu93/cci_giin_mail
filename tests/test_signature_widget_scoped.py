class _FakeSession:
    def close(self):
        pass


class _Signature:
    def __init__(self, id, name, body="", is_default=False):
        self.id = id
        self.name = name
        self.body = body
        self.is_default = is_default


def test_signature_widget_loads_only_given_staff_signatures(qtbot, monkeypatch):
    calls = []

    def fake_get_signatures(session, staff_id):
        calls.append(staff_id)
        return [_Signature(1, "自分の署名")] if staff_id == 5 else []

    monkeypatch.setattr("app.ui.settings_tab.get_session", lambda: _FakeSession())
    monkeypatch.setattr("app.ui.settings_tab.get_signatures", fake_get_signatures)

    from app.ui.settings_tab import _SignatureWidget
    w = _SignatureWidget(staff_id=5)
    qtbot.addWidget(w)

    assert calls == [5]
    assert w._table.rowCount() == 1
    assert w._table.item(0, 0).text() == "自分の署名"


def test_signature_widget_with_no_staff_id_shows_nothing(qtbot, monkeypatch):
    monkeypatch.setattr("app.ui.settings_tab.get_session", lambda: _FakeSession())

    def fail_if_called(session, staff_id):
        raise AssertionError("staff_id が None のときは get_signatures を呼ばないこと")

    monkeypatch.setattr("app.ui.settings_tab.get_signatures", fail_if_called)

    from app.ui.settings_tab import _SignatureWidget
    w = _SignatureWidget(staff_id=None)
    qtbot.addWidget(w)

    assert w._table.rowCount() == 0


def test_add_signature_uses_staff_id(qtbot, monkeypatch):
    monkeypatch.setattr("app.ui.settings_tab.get_session", lambda: _FakeSession())
    monkeypatch.setattr("app.ui.settings_tab.get_signatures", lambda s, sid: [])
    created = {}

    def fake_create_signature(session, name, body, staff_id, is_default=False):
        created["args"] = (name, body, staff_id)

    monkeypatch.setattr("app.ui.settings_tab.create_signature", fake_create_signature)

    from app.ui.settings_tab import _SignatureWidget
    w = _SignatureWidget(staff_id=7)
    qtbot.addWidget(w)
    w._name.setText("テスト署名")
    w._body.setPlainText("本文")
    w._add()

    assert created["args"] == ("テスト署名", "本文", 7)


def test_add_signature_without_staff_id_shows_warning(qtbot, monkeypatch):
    monkeypatch.setattr("app.ui.settings_tab.get_session", lambda: _FakeSession())

    def fail_if_called(session, staff_id):
        raise AssertionError("呼ばれないこと")

    monkeypatch.setattr("app.ui.settings_tab.get_signatures", fail_if_called)

    from PyQt6.QtWidgets import QMessageBox
    warned = []
    monkeypatch.setattr(QMessageBox, "warning",
                        staticmethod(lambda *a, **k: warned.append(True)))

    from app.ui.settings_tab import _SignatureWidget
    w = _SignatureWidget(staff_id=None)
    qtbot.addWidget(w)
    w._name.setText("テスト署名")
    w._body.setPlainText("本文")
    w._add()

    assert warned
