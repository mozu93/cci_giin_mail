# tests/test_send_tab_wildcard_match.py
import os
import pytest
from PyQt6.QtWidgets import QDialog


class _Email:
    def __init__(self, address):
        self.address = address


class _Member:
    def __init__(self, id, member_number, org_name):
        self.id = id
        self.member_number = member_number
        self.organization_name = org_name
        self.organization_kana = ""
        self.name = "テスト太郎"
        self.name_kana = ""
        self.title = ""
        self.position = None
        self.email_addresses = [_Email(f"{member_number}@example.com")]


class _FakeSession:
    def close(self):
        pass


def _patch_common(monkeypatch):
    monkeypatch.setattr("app.ui.send_tab.get_session", lambda: _FakeSession())
    monkeypatch.setattr("app.ui.send_tab.get_positions", lambda s: [])
    monkeypatch.setattr("app.ui.send_tab.get_committees", lambda s: [])
    monkeypatch.setattr("app.ui.send_tab.get_templates", lambda s: [])
    monkeypatch.setattr("app.ui.send_tab.get_signatures", lambda s: [])
    monkeypatch.setattr("app.ui.send_tab.get_default_signature", lambda s: None)
    monkeypatch.setattr("app.ui.send_tab.get_staff_by_name", lambda s, name: None)


def test_wildcard_matching_attaches_multiple_files_per_member(qtbot, monkeypatch, tmp_path):
    members = [_Member(1, "A001", "org1"), _Member(2, "A002", "org2")]
    _patch_common(monkeypatch)
    monkeypatch.setattr("app.ui.send_tab.get_members", lambda s: members)

    (tmp_path / "A001_請求書.pdf").write_text("dummy")
    (tmp_path / "A001_確認書_org1.pdf").write_text("dummy")
    (tmp_path / "他社ファイル.pdf").write_text("dummy")

    from app.ui.send_tab import SendTab
    tab = SendTab(staff_name="担当者A")
    qtbot.addWidget(tab)

    tab._recipient.set_checks_by_member_ids({1, 2})
    tab._individual_folder = str(tmp_path)
    tab._rule_edit.setText("{会員番号}_*.pdf")

    monkeypatch.setattr(QDialog, "exec", lambda self: True)

    tab._check_matching()

    by_number = {r["member_number"]: r for r in tab._attach_list}
    assert sorted(os.path.basename(p) for p in by_number["A001"]["filepaths"]) == [
        "A001_確認書_org1.pdf", "A001_請求書.pdf"]
    assert by_number["A001"]["found"] is True
    assert by_number["A002"]["filepaths"] == []
    assert by_number["A002"]["found"] is False


def test_build_targets_passes_all_matched_files(qtbot, monkeypatch):
    members = [_Member(1, "A001", "org1")]
    _patch_common(monkeypatch)
    monkeypatch.setattr("app.ui.send_tab.get_members", lambda s: members)
    monkeypatch.setattr(
        "app.ui.send_tab.compile_send_targets",
        lambda **kwargs: kwargs["attach_map"])

    from app.ui.send_tab import SendTab
    tab = SendTab(staff_name="担当者A")
    qtbot.addWidget(tab)
    tab._recipient.set_checks_by_member_ids({1})
    tab._attach_list = [{
        "member_number": "A001", "org_name": "org1", "to_address": "a@example.com",
        "filepaths": ["/tmp/A001_請求書.pdf", "/tmp/A001_確認書_org1.pdf"],
        "found": True,
    }]
    tab._individual_folder = "/tmp"
    tab._chk_use_attach.setChecked(True)

    result = tab._build_targets()
    assert result["A001"] == ["/tmp/A001_請求書.pdf", "/tmp/A001_確認書_org1.pdf"]


def test_build_targets_excludes_attachments_when_checkbox_unchecked(qtbot, monkeypatch):
    members = [_Member(1, "A001", "org1")]
    _patch_common(monkeypatch)
    monkeypatch.setattr("app.ui.send_tab.get_members", lambda s: members)
    monkeypatch.setattr(
        "app.ui.send_tab.compile_send_targets",
        lambda **kwargs: kwargs["attach_map"])

    from app.ui.send_tab import SendTab
    tab = SendTab(staff_name="担当者A")
    qtbot.addWidget(tab)
    tab._recipient.set_checks_by_member_ids({1})
    tab._attach_list = [{
        "member_number": "A001", "org_name": "org1", "to_address": "a@example.com",
        "filepaths": ["/tmp/A001_請求書.pdf", "/tmp/A001_確認書_org1.pdf"],
        "found": True,
    }]
    tab._individual_folder = "/tmp"

    # 「添付ファイルを使用する」チェックボックスは初期状態でオフ
    assert tab._chk_use_attach.isChecked() is False

    result = tab._build_targets()
    assert result == {}, "チェックボックスがオフの場合は添付を送信対象に含めない"
    # 内部データ自体はクリアされない（再度チェックすれば復元される）
    assert tab._attach_list[0]["filepaths"] == [
        "/tmp/A001_請求書.pdf", "/tmp/A001_確認書_org1.pdf"]

    tab._chk_use_attach.setChecked(True)
    result2 = tab._build_targets()
    assert result2["A001"] == ["/tmp/A001_請求書.pdf", "/tmp/A001_確認書_org1.pdf"]


def test_build_targets_uses_first_company_address_as_to_and_rest_as_cc(
        qtbot, monkeypatch):
    member = _Member(1, "A001", "org1")
    member.email_addresses = [
        _Email("representative@example.com"),
        _Email("manager@example.com"),
        _Email("accounting@example.com"),
    ]
    _patch_common(monkeypatch)
    monkeypatch.setattr("app.ui.send_tab.get_members", lambda s: [member])

    from app.ui.send_tab import SendTab
    tab = SendTab(staff_name="担当者A")
    qtbot.addWidget(tab)
    tab._recipient.set_checks_by_member_ids({1})
    tab._cc_edit.setText("common@example.com")

    targets = tab._build_targets()

    assert len(targets) == 1
    assert targets[0]["to_address"] == "representative@example.com"
    assert targets[0]["cc_addresses"] == [
        "manager@example.com", "accounting@example.com", "common@example.com"]


def test_build_targets_blocks_address_shared_by_different_companies(
        qtbot, monkeypatch):
    member_a = _Member(1, "A001", "A社")
    member_a.email_addresses = [
        _Email("a@example.com"), _Email("shared@example.com")]
    member_b = _Member(2, "B002", "B社")
    member_b.email_addresses = [_Email("SHARED@example.com")]
    members = [member_a, member_b]
    _patch_common(monkeypatch)
    monkeypatch.setattr("app.ui.send_tab.get_members", lambda s: members)

    from app.ui.send_tab import SendTab
    tab = SendTab(staff_name="担当者A")
    qtbot.addWidget(tab)
    tab._recipient.set_checks_by_member_ids({1, 2})

    with pytest.raises(ValueError, match="複数企業"):
        tab._build_targets()
