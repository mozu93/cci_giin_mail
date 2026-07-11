# tests/test_send_tab_wildcard_match.py
import os
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
