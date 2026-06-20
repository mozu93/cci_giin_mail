import json
import pytest
from app.database.models import Position
from app.services.member_service import (
    create_member, update_member, delete_member, get_member,
    get_members, get_member_history, set_email_addresses, member_to_snapshot
)


def _make_position(db_session, name="議員", sort_order=10):
    pos = Position(name=name, sort_order=sort_order)
    db_session.add(pos)
    db_session.flush()
    return pos


def test_create_member(db_session):
    m = create_member(db_session, "A-001", "○○商事", "山田 太郎",
                      organization_kana="マルマルショウジ", title="代表取締役")
    assert m.id is not None
    assert m.member_number == "A-001"
    assert m.organization_name == "○○商事"


def test_create_member_duplicate_number_raises(db_session):
    create_member(db_session, "A-001", "○○商事", "山田 太郎")
    with pytest.raises(Exception):
        create_member(db_session, "A-001", "△△産業", "鈴木 花子")


def test_set_email_addresses(db_session):
    m = create_member(db_session, "A-001", "○○商事", "山田 太郎")
    set_email_addresses(db_session, m.id, [
        {"address": "yamada@example.com", "label": "本人", "sort_order": 1},
        {"address": "somu@example.com",   "label": "総務", "sort_order": 2},
    ])
    fetched = get_member(db_session, m.id)
    assert len(fetched.email_addresses) == 2
    assert fetched.email_addresses[0].address == "yamada@example.com"


def test_set_email_addresses_max_5(db_session):
    m = create_member(db_session, "A-001", "○○商事", "山田 太郎")
    with pytest.raises(ValueError, match="最大5"):
        set_email_addresses(db_session, m.id, [
            {"address": f"addr{i}@example.com", "label": "", "sort_order": i}
            for i in range(1, 7)
        ])


def test_update_member_records_history(db_session):
    m = create_member(db_session, "A-001", "○○商事", "山田 太郎")
    update_member(db_session, m.id, changed_by="田中", change_reason="社名変更",
                  organization_name="○○商事（新）")
    history = get_member_history(db_session, m.id)
    assert len(history) == 1
    assert history[0].change_reason == "社名変更"
    assert history[0].changed_by == "田中"
    snap = json.loads(history[0].snapshot)
    assert snap["organization_name"] == "○○商事"  # 変更前


def test_update_member_changes_field(db_session):
    m = create_member(db_session, "A-001", "○○商事", "山田 太郎")
    update_member(db_session, m.id, changed_by="田中", change_reason="テスト",
                  organization_name="□□工業")
    fetched = get_member(db_session, m.id)
    assert fetched.organization_name == "□□工業"


def test_delete_member(db_session):
    m = create_member(db_session, "A-001", "○○商事", "山田 太郎")
    delete_member(db_session, m.id)
    assert get_member(db_session, m.id) is None


def test_get_members_filter_by_position(db_session):
    pos = _make_position(db_session, "会頭")
    m1 = create_member(db_session, "A-001", "○○商事", "山田 太郎", position_id=pos.id)
    m2 = create_member(db_session, "A-002", "△△産業", "鈴木 花子")
    results = get_members(db_session, position_id=pos.id)
    assert len(results) == 1
    assert results[0].member_number == "A-001"


def test_get_members_keyword_search(db_session):
    create_member(db_session, "A-001", "○○商事", "山田 太郎")
    create_member(db_session, "A-002", "△△産業", "鈴木 花子")
    results = get_members(db_session, keyword="山田")
    assert len(results) == 1
    assert results[0].name == "山田 太郎"


def test_member_to_snapshot_includes_emails(db_session):
    m = create_member(db_session, "A-001", "○○商事", "山田 太郎")
    set_email_addresses(db_session, m.id, [
        {"address": "yamada@example.com", "label": "本人", "sort_order": 1}
    ])
    fetched = get_member(db_session, m.id)
    snap_str = member_to_snapshot(fetched)
    snap = json.loads(snap_str)
    assert snap["organization_name"] == "○○商事"
    assert len(snap["email_addresses"]) == 1
    assert snap["email_addresses"][0]["address"] == "yamada@example.com"
