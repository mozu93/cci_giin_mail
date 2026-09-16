# tests/test_member_recent_changes.py
from app.services.member_service import (
    create_member, update_member, get_recent_changes, get_member_history,
)
from app.utils.app_config import is_bulk_edit_mode, set_bulk_edit_mode


def test_get_recent_changes_returns_field_level_diffs_newest_first(db_session):
    m1 = create_member(db_session, "1", "A事業所", "山田太郎")
    m2 = create_member(db_session, "2", "B事業所", "田中花子")

    update_member(db_session, m1.id, changed_by="担当者A", change_reason="事業所名変更",
                 organization_name="A事業所（新）", name="山田太郎", member_number="1")
    update_member(db_session, m2.id, changed_by="担当者B", change_reason="役職名変更",
                 title="取締役", name="田中花子", organization_name="B事業所",
                 member_number="2")

    events = get_recent_changes(db_session, limit=30)

    assert len(events) == 2
    # 新しい変更（m2）が先頭
    assert events[0]["org_name"] == "B事業所"
    assert events[0]["changed_by"] == "担当者B"
    assert events[0]["changes"] == [{"field": "役職名", "old": "（なし）", "new": "取締役"}]

    assert events[1]["org_name"] == "A事業所（新）"
    assert events[1]["changes"] == [
        {"field": "事業所名", "old": "A事業所", "new": "A事業所（新）"}]


def test_get_recent_changes_skips_saves_without_actual_diff(db_session):
    """値を変えずに保存した場合は変更履歴として扱わない（差分が空なら除外）。"""
    m1 = create_member(db_session, "1", "A事業所", "山田太郎")
    update_member(db_session, m1.id, changed_by="担当者A", change_reason="変更なし保存",
                 organization_name="A事業所", name="山田太郎", member_number="1")

    events = get_recent_changes(db_session, limit=30)
    assert events == []


def test_get_recent_changes_respects_limit(db_session):
    m1 = create_member(db_session, "1", "A事業所", "山田太郎")
    for i in range(5):
        update_member(db_session, m1.id, changed_by="担当者A", change_reason="更新",
                     organization_name=f"A事業所{i}", name="山田太郎", member_number="1")

    events = get_recent_changes(db_session, limit=3)
    assert len(events) == 3


def test_committee_role_change_is_tracked_in_history(db_session):
    """委員会役職の変更も変更履歴・最近の更新の対象に含める。"""
    from app.database.models import Committee
    committee = Committee(name="総務委員会", sort_order=1)
    db_session.add(committee)
    db_session.commit()

    m1 = create_member(db_session, "1", "A事業所", "山田太郎", committee_id=committee.id)
    update_member(db_session, m1.id, changed_by="担当者A", change_reason="委員会役職登録",
                 committee_role="委員長", member_number="1",
                 organization_name="A事業所", name="山田太郎")

    events = get_recent_changes(db_session, limit=30)
    assert len(events) == 1
    assert events[0]["changes"] == [
        {"field": "委員会役職", "old": "（なし）", "new": "委員長"}]


def test_bulk_edit_mode_keeps_history_but_hides_from_recent(db_session):
    """一括変更モード中の変更は、履歴には残るが「最近の更新」には出ない。"""
    assert is_bulk_edit_mode() is False  # 既定はオフ

    m1 = create_member(db_session, "1", "A事業所", "山田太郎")

    set_bulk_edit_mode(True)
    try:
        update_member(db_session, m1.id, changed_by="担当者A", change_reason="一括登録",
                     name="山田次郎", member_number="1", organization_name="A事業所")
    finally:
        set_bulk_edit_mode(False)

    # 履歴には残る（監査証跡は途切れない）が、最近の更新には出ない
    assert len(get_member_history(db_session, m1.id)) == 1
    assert get_recent_changes(db_session, limit=30) == []

    # オフに戻せば通常どおり一覧に出る
    update_member(db_session, m1.id, changed_by="担当者B", change_reason="通常更新",
                 name="山田三郎", member_number="1", organization_name="A事業所")
    assert len(get_member_history(db_session, m1.id)) == 2
    events = get_recent_changes(db_session, limit=30)
    assert len(events) == 1
    assert events[0]["changed_by"] == "担当者B"
    assert events[0]["changes"] == [
        {"field": "氏名", "old": "山田次郎", "new": "山田三郎"}]


def test_bulk_edit_changes_are_not_merged_into_earlier_event(db_session):
    """一括変更モード中の変更が、直前の通常変更の差分に混ざらないこと（誤帰属の回帰テスト）。"""
    m1 = create_member(db_session, "1", "A事業所", "山田太郎")

    # 通常の変更（記録あり・一覧に出る）
    update_member(db_session, m1.id, changed_by="担当者A", change_reason="事業所名変更",
                 organization_name="A事業所（新）", name="山田太郎", member_number="1")

    # 一括変更モード中の変更（一覧には出ない）
    set_bulk_edit_mode(True)
    try:
        update_member(db_session, m1.id, changed_by="担当者B", change_reason="一括登録",
                     title="委員長", organization_name="A事業所（新）",
                     name="山田太郎", member_number="1")
    finally:
        set_bulk_edit_mode(False)

    events = get_recent_changes(db_session, limit=30)
    assert len(events) == 1
    # 一括変更分（役職名）が事業所名変更の行に混ざらない
    assert events[0]["changed_by"] == "担当者A"
    assert events[0]["changes"] == [
        {"field": "事業所名", "old": "A事業所", "new": "A事業所（新）"}]
