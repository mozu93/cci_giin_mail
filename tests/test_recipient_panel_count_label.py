from app.ui.recipient_panel import RecipientPanel


class _Email:
    def __init__(self, address):
        self.address = address


class _Member:
    def __init__(self, id, org_name, emails=None):
        self.id = id
        self.member_number = f"A-{id:03d}"
        self.organization_name = org_name
        self.organization_kana = ""
        self.name = "テスト太郎"
        self.name_kana = ""
        self.title = ""
        self.position = None
        self.email_addresses = [_Email(a) for a in (emails or [])]


def test_count_label_shows_company_count_separately_from_row_count(qtbot):
    panel = RecipientPanel()
    qtbot.addWidget(panel)
    panel.load_members([
        _Member(1, "対象商事", emails=["a@example.com", "b@example.com"]),
        _Member(2, "除外商事", emails=["c@example.com"]),
    ])

    panel.set_checks_by_member_ids({1, 2})

    # 対象商事はメール2件、除外商事は1件 → 行数(件)は3、社数は2
    assert panel._count_label.text() == "2社 3件選択"


def test_count_label_resets_to_zero_when_cleared(qtbot):
    panel = RecipientPanel()
    qtbot.addWidget(panel)
    panel.load_members([
        _Member(1, "対象商事", emails=["a@example.com", "b@example.com"]),
    ])

    panel.set_checks_by_member_ids({1})
    assert panel._count_label.text() == "1社 2件選択"

    panel.clear_checks()
    assert panel._count_label.text() == "0社 0件選択"
