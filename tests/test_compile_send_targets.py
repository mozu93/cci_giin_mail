"""compile_send_targets() の単体テスト。

テスト対象のビジネスルール:
- 会員フィールドが件名・本文に差し込まれる
- merge_data の col1-col5 が差し込まれる
- col_labels でラベルエイリアスが機能する
- to_address が空文字のまま渡される（メール無し）
- 共通添付 + 個別添付が合算される
- member_number が attach_map にない場合は共通添付のみ
"""
import pytest
from unittest.mock import MagicMock
from app.services.email_service import compile_send_targets


def _make_member(
    member_id: int = 1,
    member_number: str = "A-001",
    organization_name: str = "○○商事",
    title: str = "代表取締役",
    name: str = "山田 太郎",
    position_name: str = "議員",
):
    m = MagicMock()
    m.id = member_id
    m.member_number = member_number
    m.organization_name = organization_name
    m.title = title
    m.name = name
    m.position.name = position_name
    return m


# ─── 基本的な差し込み ───────────────────────────────────────


def test_member_fields_substituted():
    member = _make_member(
        organization_name="テスト商事",
        title="社長",
        name="テスト 太郎",
        position_name="副会頭",
    )
    rows = [{"member": member, "to_address": "test@example.com"}]
    result = compile_send_targets(
        checked_rows=rows,
        subject_tpl="{事業所名}御中",
        body_tpl="{役職名} {氏名}様\n会議所役職: {会議所役職名}",
        sig_body="",
        merge_data={},
        col_labels={},
        common_attachments=[],
        attach_map={},
    )
    assert len(result) == 1
    t = result[0]
    assert t["subject"] == "テスト商事御中"
    assert t["body"] == "社長 テスト 太郎様\n会議所役職: 副会頭"
    assert t["to_address"] == "test@example.com"
    assert t["org_name"] == "テスト商事"
    assert t["member_id"] == 1


def test_sig_body_appended():
    member = _make_member()
    rows = [{"member": member, "to_address": "a@b.com"}]
    result = compile_send_targets(
        checked_rows=rows,
        subject_tpl="件名",
        body_tpl="本文",
        sig_body="\n\n--\n署名テスト",
        merge_data={},
        col_labels={},
        common_attachments=[],
        attach_map={},
    )
    assert result[0]["body"] == "本文\n\n--\n署名テスト"


# ─── 差し込みデータ ──────────────────────────────────────────


def test_merge_col_substitution():
    member = _make_member(member_number="A-001")
    rows = [{"member": member, "to_address": "x@y.com"}]
    result = compile_send_targets(
        checked_rows=rows,
        subject_tpl="{col1}会議",
        body_tpl="{col2}にて開催",
        sig_body="",
        merge_data={"A-001": {"col1": "定期総会", "col2": "来月"}},
        col_labels={},
        common_attachments=[],
        attach_map={},
    )
    assert result[0]["subject"] == "定期総会会議"
    assert result[0]["body"] == "来月にて開催"


def test_merge_col_missing_becomes_empty():
    member = _make_member(member_number="A-001")
    rows = [{"member": member, "to_address": "x@y.com"}]
    result = compile_send_targets(
        checked_rows=rows,
        subject_tpl="{col3}",
        body_tpl="{col4}{col5}",
        sig_body="",
        merge_data={},
        col_labels={},
        common_attachments=[],
        attach_map={},
    )
    assert result[0]["subject"] == ""
    assert result[0]["body"] == ""


def test_col_labels_does_not_break_col_substitution():
    """col_labels を渡しても {col1} の通常置換は正常に動作する。
    col_labels はステータスバーのヒント表示用であり、独自プレースホルダーは作らない。
    """
    member = _make_member(member_number="B-001")
    rows = [{"member": member, "to_address": "x@y.com"}]
    result = compile_send_targets(
        checked_rows=rows,
        subject_tpl="{col1}のご案内",
        body_tpl="",
        sig_body="",
        merge_data={"B-001": {"col1": "春季総会"}},
        col_labels={"col1": "会議名"},
        common_attachments=[],
        attach_map={},
    )
    assert result[0]["subject"] == "春季総会のご案内"


# ─── メール無し ──────────────────────────────────────────────


def test_no_email_address_preserved_as_empty():
    """to_address="" のままターゲットに含まれる（送信時スキップは呼び出し元の責任）"""
    member = _make_member()
    rows = [{"member": member, "to_address": ""}]
    result = compile_send_targets(
        checked_rows=rows,
        subject_tpl="件名",
        body_tpl="本文",
        sig_body="",
        merge_data={},
        col_labels={},
        common_attachments=[],
        attach_map={},
    )
    assert len(result) == 1
    assert result[0]["to_address"] == ""


# ─── 添付ファイル ────────────────────────────────────────────


def test_common_attachments_applied_to_all():
    m1 = _make_member(member_id=1, member_number="A-001")
    m2 = _make_member(member_id=2, member_number="A-002")
    rows = [
        {"member": m1, "to_address": "a@b.com"},
        {"member": m2, "to_address": "c@d.com"},
    ]
    result = compile_send_targets(
        checked_rows=rows,
        subject_tpl="",
        body_tpl="",
        sig_body="",
        merge_data={},
        col_labels={},
        common_attachments=["common.pdf"],
        attach_map={},
    )
    assert result[0]["attachments"] == ["common.pdf"]
    assert result[1]["attachments"] == ["common.pdf"]


def test_individual_attach_combined_with_common():
    member = _make_member(member_number="A-001")
    rows = [{"member": member, "to_address": "a@b.com"}]
    result = compile_send_targets(
        checked_rows=rows,
        subject_tpl="",
        body_tpl="",
        sig_body="",
        merge_data={},
        col_labels={},
        common_attachments=["common.pdf"],
        attach_map={"A-001": ["A001_indiv.pdf"]},
    )
    assert result[0]["attachments"] == ["common.pdf", "A001_indiv.pdf"]


def test_no_individual_attach_for_other_member():
    m1 = _make_member(member_id=1, member_number="A-001")
    m2 = _make_member(member_id=2, member_number="A-002")
    rows = [
        {"member": m1, "to_address": "a@b.com"},
        {"member": m2, "to_address": "c@d.com"},
    ]
    result = compile_send_targets(
        checked_rows=rows,
        subject_tpl="",
        body_tpl="",
        sig_body="",
        merge_data={},
        col_labels={},
        common_attachments=["common.pdf"],
        attach_map={"A-001": ["A001_indiv.pdf"]},
    )
    assert result[0]["attachments"] == ["common.pdf", "A001_indiv.pdf"]
    assert result[1]["attachments"] == ["common.pdf"]


# ─── 空入力 ──────────────────────────────────────────────────


def test_empty_checked_rows_returns_empty():
    result = compile_send_targets(
        checked_rows=[],
        subject_tpl="件名",
        body_tpl="本文",
        sig_body="",
        merge_data={},
        col_labels={},
        common_attachments=[],
        attach_map={},
    )
    assert result == []
