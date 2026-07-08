from app.ui.recipient_panel import RecipientPanel


class _Member:
    def __init__(self, id, org_name):
        self.id = id
        self.member_number = f"A-{id:03d}"
        self.organization_name = org_name
        self.organization_kana = ""
        self.name = "テスト太郎"
        self.name_kana = ""
        self.title = ""
        self.position = None
        self.email_addresses = []


def test_select_all_visible_only_checks_unhidden_rows(qtbot):
    panel = RecipientPanel()
    qtbot.addWidget(panel)
    panel.load_members([_Member(1, "対象商事"), _Member(2, "除外商事")])

    panel.filter("対象")  # 除外商事の行を非表示にする
    panel.select_all_visible()

    checked_orgs = [m.organization_name for m in panel.get_selected_members()]
    assert checked_orgs == ["対象商事"]


def test_clear_visible_unchecks_only_visible_rows(qtbot):
    panel = RecipientPanel()
    qtbot.addWidget(panel)
    panel.load_members([_Member(1, "対象商事"), _Member(2, "除外商事")])
    panel.set_checks_by_member_ids({1, 2})

    panel.filter("対象")
    panel.clear_visible()

    checked_orgs = {m.organization_name for m in panel.get_selected_members()}
    assert checked_orgs == {"除外商事"}
