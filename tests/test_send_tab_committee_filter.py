class _Member:
    def __init__(self, id, committee_id):
        self.id = id
        self.member_number = f"A-{id:03d}"
        self.organization_name = f"org{id}"
        self.organization_kana = ""
        self.name = "テスト太郎"
        self.name_kana = ""
        self.title = ""
        self.position = None
        self.position_id = None
        self.committee_id = committee_id
        self.email_addresses = []


class _Committee:
    def __init__(self, id, name):
        self.id = id
        self.name = name


class _FakeSession:
    def close(self):
        pass


def test_committee_filter_checks_only_matching_members(qtbot, monkeypatch):
    committees = [_Committee(1, "総務・運営委員会"), _Committee(2, "地域経済推進委員会")]
    members = [_Member(1, committee_id=1), _Member(2, committee_id=2),
               _Member(3, committee_id=None)]

    monkeypatch.setattr("app.ui.send_tab.get_session", lambda: _FakeSession())
    monkeypatch.setattr("app.ui.send_tab.get_positions", lambda s: [])
    monkeypatch.setattr("app.ui.send_tab.get_committees", lambda s: committees)
    monkeypatch.setattr("app.ui.send_tab.get_members", lambda s: members)
    monkeypatch.setattr("app.ui.send_tab.get_templates", lambda s: [])
    monkeypatch.setattr("app.ui.send_tab.get_signatures", lambda s: [])
    monkeypatch.setattr("app.ui.send_tab.get_default_signature", lambda s: None)

    from app.ui.send_tab import SendTab
    tab = SendTab(staff_name="担当者A")
    qtbot.addWidget(tab)

    tab._rb_by_committee.setChecked(True)
    tab._committee_list.setCurrentRow(0)  # 総務・運営委員会を選択

    selected = tab._recipient.get_selected_members()
    assert [m.id for m in selected] == [1]
