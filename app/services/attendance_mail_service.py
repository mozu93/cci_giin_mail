import re
from sqlalchemy.orm import Session
from app.database.models import Member

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
