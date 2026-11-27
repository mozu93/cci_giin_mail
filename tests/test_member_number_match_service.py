import pytest

from app.services.member_number_match_service import (
    MODE_MATCHED, MODE_UNMATCHED, extract_numbers, match_member_numbers,
    normalize_member_number, resolve_target_ids,
)
from app.services.member_service import create_member, get_members


def _members(db_session):
    a = create_member(db_session, "A-001", "○○商事", "山田太郎")
    b = create_member(db_session, "002", "△△産業", "鈴木花子")
    c = create_member(db_session, "A-003", "□□工業", "佐藤次郎")
    return a, b, c


def test_normalize_handles_width_space_case_and_float():
    assert normalize_member_number(" ａ－００１ ") == "a-001"
    assert normalize_member_number(12.0) == "12"
    assert normalize_member_number(None) == ""


def test_extract_numbers_skips_header_and_blank():
    rows = [["会員番号", "名前"], ["A-001", "x"], ["", "y"], [2.0, "z"], ["A-003"]]
    assert extract_numbers(rows, 0, True) == ["A-001", "2", "A-003"]
    assert extract_numbers(rows, 0, False)[0] == "会員番号"
    assert extract_numbers(rows, 1, True) == ["x", "y", "z"]


def test_match_exact_and_leading_zero(db_session):
    a, b, c = _members(db_session)
    members = get_members(db_session)
    r = match_member_numbers(db_session, ["a-001", "2"], members)
    assert r.matched_ids == {a.id, b.id}
    assert r.not_found == [] and r.total == 2


def test_match_reports_not_found_inactive_and_duplicates(db_session):
    a, b, c = _members(db_session)
    c.is_active = False
    db_session.commit()
    members = get_members(db_session)
    r = match_member_numbers(
        db_session, ["A-001", "A-001", "A-003", "ZZZ-9"], members)
    assert r.matched_ids == {a.id}
    assert r.inactive == ["A-003"]
    assert r.not_found == ["ZZZ-9"]
    assert r.duplicates == 1 and r.total == 3


def test_resolve_target_ids_matched_and_unmatched(db_session):
    a, b, c = _members(db_session)
    members = get_members(db_session)
    r = match_member_numbers(db_session, ["A-001"], members)
    assert resolve_target_ids(members, r, MODE_MATCHED) == {a.id}
    assert resolve_target_ids(members, r, MODE_UNMATCHED) == {b.id, c.id}
    with pytest.raises(ValueError):
        resolve_target_ids(members, r, "x")
