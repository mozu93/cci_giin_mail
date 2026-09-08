from app.ui.send_tab import (
    _split_oversized_targets, _duplicate_recipient_groups,
    _recipient_conflicts, _cross_company_recipient_conflicts,
    _validate_company_attachment_rule, _validate_company_attachment_files,
)
from app.services.email_service import ATTACHMENT_SIZE_LIMIT_BYTES
import pytest


def test_split_oversized_targets_separates_over_limit(tmp_path):
    small = tmp_path / "small.pdf"
    small.write_bytes(b"x" * 100)
    big = tmp_path / "big.pdf"
    big.write_bytes(b"y" * (ATTACHMENT_SIZE_LIMIT_BYTES + 1))

    targets = [
        {"org_name": "小さい会社", "attachments": [str(small)]},
        {"org_name": "大きい会社", "attachments": [str(big)]},
    ]
    ok, oversized = _split_oversized_targets(targets)
    assert [t["org_name"] for t in ok] == ["小さい会社"]
    assert [t["org_name"] for t in oversized] == ["大きい会社"]


def test_split_oversized_targets_empty_attachments_is_ok():
    targets = [{"org_name": "添付なし", "attachments": []}]
    ok, oversized = _split_oversized_targets(targets)
    assert len(ok) == 1
    assert oversized == []


def test_duplicate_recipient_groups_is_case_insensitive():
    targets = [
        {"to_address": "Info@Example.jp", "org_name": "A社"},
        {"to_address": " info@example.jp ", "org_name": "B社"},
        {"to_address": "other@example.jp", "org_name": "C社"},
    ]
    groups = _duplicate_recipient_groups(targets)
    assert len(groups) == 1
    assert [item["org_name"] for item in groups[0]] == ["A社", "B社"]


def test_recipient_conflicts_detects_duplicates_across_to_cc_bcc():
    targets = [{
        "org_name": "A社",
        "to_address": "Info@Example.jp",
        "cc_addresses": ["staff@example.jp", "info@example.jp"],
        "bcc_addresses": ["STAFF@example.jp"],
    }]

    conflicts = _recipient_conflicts(targets)

    assert len(conflicts) == 2
    assert any("ToとCC" in item for item in conflicts)
    assert any("CCとBCC" in item for item in conflicts)


def test_recipient_conflicts_accepts_unique_recipients():
    targets = [{
        "org_name": "A社",
        "to_address": "info@example.jp",
        "cc_addresses": ["staff@example.jp"],
        "bcc_addresses": ["archive@example.jp"],
    }]
    assert _recipient_conflicts(targets) == []


class _Email:
    def __init__(self, address):
        self.address = address


class _Member:
    def __init__(self, member_id, organization_name, addresses):
        self.id = member_id
        self.organization_name = organization_name
        self.email_addresses = [_Email(address) for address in addresses]


def test_cross_company_conflicts_detects_to_and_cc_reuse():
    members = [
        _Member(1, "A社", ["a@example.com", "shared@example.com"]),
        _Member(2, "B社", ["SHARED@example.com"]),
    ]
    conflicts = _cross_company_recipient_conflicts(members)
    assert conflicts == ["SHARED@example.com: A社 と B社"]


def test_cross_company_conflicts_accepts_addresses_within_one_company():
    members = [_Member(1, "A社", ["a@example.com", "b@example.com"])]
    assert _cross_company_recipient_conflicts(members) == []


@pytest.mark.parametrize("rule", ["*.pdf", "../{会員番号}_*.pdf", "sub\\{会員番号}_*.pdf"])
def test_company_attachment_rule_rejects_unsafe_patterns(rule):
    with pytest.raises(ValueError):
        _validate_company_attachment_rule(rule)


def test_company_attachment_rule_accepts_member_number_prefix():
    _validate_company_attachment_rule("{会員番号}_*.pdf")


def test_company_attachment_files_rejects_other_company_file(tmp_path):
    other_file = tmp_path / "B002_請求書.pdf"
    other_file.write_bytes(b"pdf")
    rows = [{
        "member_number": "A001",
        "filepaths": [str(other_file)],
    }]
    with pytest.raises(ValueError, match="別企業"):
        _validate_company_attachment_files(rows, str(tmp_path), {"A001"})


def test_company_attachment_files_rejects_file_outside_selected_folder(tmp_path):
    selected_folder = tmp_path / "selected"
    selected_folder.mkdir()
    outside_file = tmp_path / "A001_請求書.pdf"
    outside_file.write_bytes(b"pdf")
    rows = [{
        "member_number": "A001",
        "filepaths": [str(outside_file)],
    }]
    with pytest.raises(ValueError, match="別企業"):
        _validate_company_attachment_files(
            rows, str(selected_folder), {"A001"})


def test_company_attachment_files_accepts_matching_file(tmp_path):
    matching_file = tmp_path / "A001_請求書.pdf"
    matching_file.write_bytes(b"pdf")
    rows = [{
        "member_number": "A001",
        "filepaths": [str(matching_file)],
    }]
    _validate_company_attachment_files(rows, str(tmp_path), {"A001"})
