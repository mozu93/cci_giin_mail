import re
from dataclasses import dataclass
from sqlalchemy.orm import Session
from app.database.models import Member, AttendanceRecord

STATUS_MAP = {
    "出席": "出席",
    "出席(※代理)": "代理",
    "委任": "委任",
    "欠席": "欠席",
}

_ORG_SUFFIXES = ["株式会社", "有限会社", "合同会社", "㈱", "（株）", "(株)"]

_FIELD_LABELS = {
    "status_raw":   "出欠",
    "org_name":     "事業所名",
    "name":         "氏名",
    "proxy_title":  "代理役職",
    "proxy_name":   "代理者名",
    "notes":        "備考",
}


def _label_pattern(label: str) -> str:
    return r"\s*".join(re.escape(ch) for ch in label)


def _extract(body_text: str, label: str) -> str:
    pattern = r"【" + _label_pattern(label) + r"】\s*(.*?)(?=【|\Z)"
    m = re.search(pattern, body_text, re.DOTALL)
    if not m:
        return ""
    return m.group(1).strip()


def parse_body(body_text: str) -> dict:
    """メール本文から【ラベル】: 値 形式の各項目を抽出する。"""
    return {key: _extract(body_text, label) for key, label in _FIELD_LABELS.items()}


def normalize_org_name(name: str) -> str:
    """会員突合用に事業所名を正規化する（法人格表記・空白を除去）。"""
    result = name
    for suf in _ORG_SUFFIXES:
        result = result.replace(suf, "")
    result = re.sub(r"\s+", "", result)
    return result


def match_member(session: Session, org_name_raw: str) -> Member | None:
    """事業所名を正規化して一意に一致する会員を返す。0件/複数件一致はNone。"""
    target = normalize_org_name(org_name_raw)
    members = session.query(Member).filter(Member.is_active == True).all()
    matches = [m for m in members if normalize_org_name(m.organization_name) == target]
    if len(matches) == 1:
        return matches[0]
    return None


@dataclass
class AttendanceMailRow:
    message_id: str
    org_name_raw: str
    name_raw: str
    status: str
    proxy_title: str
    proxy_name: str
    notes: str
    matched_member: Member | None
    existing_status: str | None


def build_preview(session: Session, meeting_id: int,
                  messages: list[dict]) -> list[AttendanceMailRow]:
    """メールを解析・会員突合し、同一会員宛の重複は最新のみ残す。

    messages は受信日時の古い順であること（fetch_messagesの契約）。
    同じ辞書キー（正規化した事業所名）に対して後から来たものが上書きする
    ことで、常に最新のメールだけが残る。
    """
    by_org: dict[str, AttendanceMailRow] = {}
    for msg in messages:
        fields = parse_body(msg["body_text"])
        member = match_member(session, fields["org_name"])
        row = AttendanceMailRow(
            message_id=msg["id"],
            org_name_raw=fields["org_name"],
            name_raw=fields["name"],
            status=STATUS_MAP.get(fields["status_raw"], ""),
            proxy_title=fields["proxy_title"],
            proxy_name=fields["proxy_name"],
            notes=fields["notes"],
            matched_member=member,
            existing_status=None,
        )
        key = normalize_org_name(fields["org_name"])
        by_org[key] = row

    rows = list(by_org.values())
    for row in rows:
        if row.matched_member is not None:
            existing = (session.query(AttendanceRecord)
                       .filter_by(meeting_id=meeting_id,
                                  member_id=row.matched_member.id)
                       .first())
            row.existing_status = existing.status if existing else None
    return rows
