"""会員番号の一覧（CSV/Excel）を読み込み、送信先として選ぶ会員を決める。"""
import re
import unicodedata
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.database.models import Member

MODE_MATCHED = "matched"      # 一致した会員を選ぶ
MODE_UNMATCHED = "unmatched"  # 一致しなかった会員を選ぶ（一覧を除外リストとして使う）


@dataclass
class MemberNumberMatch:
    matched_ids: set[int] = field(default_factory=set)
    not_found: list[str] = field(default_factory=list)  # 名簿に存在しない番号
    inactive: list[str] = field(default_factory=list)   # 退任済み（非アクティブ）
    duplicates: int = 0                                 # 一覧内の重複番号の数
    total: int = 0                                      # 重複を除いた番号の数


def normalize_member_number(value) -> str:
    """表記ゆれ（全角半角・空白・大文字小文字）を吸収した比較用の文字列にする。"""
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        value = int(value)  # Excelの数値セルが 123.0 になるのを防ぐ
    text = unicodedata.normalize("NFKC", str(value))
    return re.sub(r"\s+", "", text).casefold()


def _loose_key(normalized: str) -> str | None:
    """数字だけの番号は先頭ゼロの有無を無視して比較する（Excelが 001 を 1 にするため）。"""
    if normalized.isdigit():
        return normalized.lstrip("0") or "0"
    return None


def extract_numbers(rows: list[list], column: int, has_header: bool) -> list[str]:
    """行リストから指定列の会員番号を取り出す（空欄は除く）。"""
    body = rows[1:] if has_header else rows
    numbers = []
    for row in body:
        if column >= len(row):
            continue
        value = row[column]
        if isinstance(value, float) and value.is_integer():
            value = int(value)
        text = str(value).strip() if value is not None else ""
        if text:
            numbers.append(text)
    return numbers


def match_member_numbers(session: Session, numbers: list[str],
                         members: list[Member]) -> MemberNumberMatch:
    """番号一覧を、送信先候補(members)の会員番号と照合する。

    members に無い番号のうち、退任済み会員のものは inactive、
    名簿にも無いものは not_found に分けて返す。"""
    exact: dict[str, Member] = {}
    loose: dict[str, Member] = {}
    for m in members:
        key = normalize_member_number(m.member_number)
        exact.setdefault(key, m)
        lk = _loose_key(key)
        if lk is not None:
            loose.setdefault(lk, m)

    inactive_keys: set[str] = set()
    for (number,) in (session.query(Member.member_number)
                      .filter(Member.is_active == False).all()):  # noqa: E712
        key = normalize_member_number(number)
        inactive_keys.add(key)
        lk = _loose_key(key)
        if lk is not None:
            inactive_keys.add("loose:" + lk)

    result = MemberNumberMatch()
    seen: set[str] = set()
    for raw in numbers:
        key = normalize_member_number(raw)
        if not key:
            continue
        if key in seen:
            result.duplicates += 1
            continue
        seen.add(key)
        result.total += 1
        lk = _loose_key(key)
        member = exact.get(key) or (loose.get(lk) if lk is not None else None)
        if member is not None:
            result.matched_ids.add(member.id)
        elif key in inactive_keys or (lk is not None and "loose:" + lk in inactive_keys):
            result.inactive.append(raw)
        else:
            result.not_found.append(raw)
    return result


def resolve_target_ids(members: list[Member], match: MemberNumberMatch,
                       mode: str) -> set[int]:
    """モードに応じて、チェックを入れる会員IDを返す。"""
    if mode == MODE_MATCHED:
        return set(match.matched_ids)
    if mode == MODE_UNMATCHED:
        return {m.id for m in members} - match.matched_ids
    raise ValueError(f"不明なモード: {mode}")
