import re
import requests
from dataclasses import dataclass
from datetime import datetime
from sqlalchemy.orm import Session, joinedload
from app.database.models import (
    Member, AttendanceRecord, ProcessedAttendanceMail, Meeting,
    AttendanceMailAlias)
from app.services.email_service import get_access_token
from app.services.meeting_service import upsert_attendance

_GRAPH_BASE = "https://graph.microsoft.com/v1.0"

STATUS_MAP = {
    "出席": "出席",
    "出席(※代理)": "代理",
    "委任": "委任",
    "欠席": "欠席",
}

_ORG_SUFFIXES = ["株式会社", "有限会社", "合同会社",
                "㈱", "（株）", "(株)",
                "㈲", "（有）", "(有)"]

# 会員データとメール本文とで表記が揺れやすい旧字体・異体字の正規化
# （例: 「三重機械鐵工」を会員データでは旧字体「鐵」、メールでは新字体「鉄」で
# 書く場合があり、そのままでは突合できないため統一する）
_CHAR_VARIANTS = {
    "鐵": "鉄",
}

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
    """会員突合用に事業所名を正規化する（法人格表記・空白・文字化け記号を除去）。

    '?' はメール送信元側で㈱記号や異体字漢字がデコードできず失われた際に
    残る印。除去しないと本来一致するはずの表記まで不一致になってしまう。
    """
    result = name
    for suf in _ORG_SUFFIXES:
        result = result.replace(suf, "")
    result = result.replace("?", "")
    for variant, standard in _CHAR_VARIANTS.items():
        result = result.replace(variant, standard)
    result = re.sub(r"\s+", "", result)
    return result


def match_member(session: Session, org_name_raw: str) -> Member | None:
    """事業所名から会員を突合する。

    1. 過去に確定させた紐付け（AttendanceMailAlias）があればそれを優先する
    2. 正規化した表記が一意に一致する会員を探す
    3. 一意な完全一致が無ければ、正規化表記が包含関係にある会員を探す
       （例: メール記載「近鉄百貨店」⊂ 会員データ「近鉄百貨店四日市店」）
    いずれも0件/複数件該当する場合はNoneを返す（要手動選択）。
    """
    target = normalize_org_name(org_name_raw)
    if not target:
        return None

    alias = session.query(AttendanceMailAlias).filter_by(org_name_key=target).first()
    if alias is not None:
        return session.get(Member, alias.member_id)

    members = session.query(Member).filter(Member.is_active == True).all()
    keyed = [(m, normalize_org_name(m.organization_name)) for m in members]
    keyed = [(m, k) for m, k in keyed if k]

    exact = [m for m, k in keyed if k == target]
    if len(exact) == 1:
        return exact[0]
    if exact:
        return None

    contains = [m for m, k in keyed if target in k or k in target]
    if len(contains) == 1:
        return contains[0]
    return None


def upsert_alias(session: Session, org_name_raw: str, member_id: int) -> None:
    """事業所名表記→会員の紐付けを記憶（既存なら上書き）する。

    誤った紐付けを直したい場合は、正しい会員を選び直して再度反映すれば
    ここで上書きされる。
    """
    key = normalize_org_name(org_name_raw)
    if not key:
        return
    alias = session.query(AttendanceMailAlias).filter_by(org_name_key=key).first()
    if alias is None:
        session.add(AttendanceMailAlias(
            org_name_key=key, org_name_raw=org_name_raw, member_id=member_id))
    else:
        alias.org_name_raw = org_name_raw
        alias.member_id = member_id


def list_aliases(session: Session) -> list[AttendanceMailAlias]:
    """登録済みの事業所名紐付けを一覧取得する（管理画面用）。"""
    return (session.query(AttendanceMailAlias)
           .options(joinedload(AttendanceMailAlias.member))
           .order_by(AttendanceMailAlias.org_name_raw)
           .all())


def delete_alias(session: Session, alias_id: int) -> None:
    """紐付けを削除する。以後は自動突合ロジックにフォールバックする。"""
    alias = session.get(AttendanceMailAlias, alias_id)
    if alias is not None:
        session.delete(alias)
        session.commit()


def update_alias_member(session: Session, alias_id: int, member_id: int) -> None:
    """誤って登録された紐付けの会員を修正する。"""
    alias = session.get(AttendanceMailAlias, alias_id)
    if alias is not None:
        alias.member_id = member_id
        session.commit()


def get_since_datetime(session: Session, meeting_id: int) -> datetime:
    """指定した会議の出欠連絡メールを検索する開始日時（会議開催月の1日）を返す。

    突合できなかった・会員未選択で反映しなかったメールを次回以降の検索で
    取りこぼさないよう、常に開催月の1日から検索する（反映済みメールの
    重複表示はexclude_ids側で防止するため、ここでは受信日時を進めない）。
    常議員会の出欠連絡は開催月内にしか来ない運用のため、検索範囲を
    月初めに固定しても性能上の問題にはならない。
    """
    meeting = session.get(Meeting, meeting_id)
    return datetime(meeting.date.year, meeting.date.month, 1)


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
    received_at: datetime


def build_preview(session: Session, meeting_id: int,
                  messages: list[dict]) -> list[AttendanceMailRow]:
    """メールを解析・会員突合し、同一会員宛の重複は最新のみ残す。

    messages は受信日時の古い順であること（fetch_messagesの契約）。
    同じ辞書キー（正規化した事業所名）に対して後から来たものが上書きする
    ことで、常に最新のメールだけが残る。事業所名を抽出できなかった
    （本文の形式が想定と異なる等の）メールは、正規化キーが空文字になり
    複数件あると互いに上書きして消えてしまうため、メッセージIDを使った
    一意なキーにして必ず一覧に残るようにする（誰にも見えずに取りこぼす
    ことがないようにするため）。
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
            received_at=msg["received_at"],
        )
        key = normalize_org_name(fields["org_name"]) or f"__unresolved__{msg['id']}"
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


def _resolve_folder_id(token: str, folder_name: str) -> str:
    """表示名からフォルダIDを解決する。

    まずトップレベルのフォルダを完全一致で探し（高速パス）、見つからなければ
    既存フォルダのサブフォルダを幅優先で再帰的に探索する。Outlookの仕分け
    ルールで作ったフォルダが受信トレイ等の下に作られているケースに対応する
    （Graph APIの /me/mailFolders は既定でトップレベルしか返さないため）。
    """
    headers = {"Authorization": f"Bearer {token}"}
    escaped_name = folder_name.replace("'", "''")
    resp = requests.get(
        f"{_GRAPH_BASE}/me/mailFolders",
        headers=headers,
        params={"$filter": f"displayName eq '{escaped_name}'"},
        timeout=30,
    )
    if resp.status_code != 200:
        raise RuntimeError(
            f"フォルダ一覧の取得に失敗しました ({resp.status_code}): {resp.text[:200]}")
    values = resp.json().get("value", [])
    if values:
        return values[0]["id"]

    resp = requests.get(
        f"{_GRAPH_BASE}/me/mailFolders",
        headers=headers,
        params={"$top": 250},
        timeout=30,
    )
    if resp.status_code != 200:
        raise RuntimeError(
            f"フォルダ一覧の取得に失敗しました ({resp.status_code}): {resp.text[:200]}")
    queue = [f["id"] for f in resp.json().get("value", [])]
    while queue:
        parent_id = queue.pop(0)
        resp = requests.get(
            f"{_GRAPH_BASE}/me/mailFolders/{parent_id}/childFolders",
            headers=headers,
            params={"$top": 250},
            timeout=30,
        )
        if resp.status_code != 200:
            continue
        for child in resp.json().get("value", []):
            if child.get("displayName") == folder_name:
                return child["id"]
            queue.append(child["id"])

    raise ValueError(
        f"フォルダ「{folder_name}」が見つかりません。Outlookのフォルダ名を確認してください。")


def _parse_graph_datetime(raw: str) -> datetime:
    """Graph APIのreceivedDateTime（UTC、小数秒桁数が可変）をnaive datetimeにする。"""
    raw = raw.rstrip("Z")
    if "." in raw:
        raw = raw.split(".")[0]
    return datetime.strptime(raw, "%Y-%m-%dT%H:%M:%S")


def fetch_messages(graph_config: dict, folder_name: str, subject_filter: str,
                   exclude_ids: set[str], since: datetime) -> list[dict]:
    """指定フォルダ内で since より後に受信したメールをGraph APIで取得する
    （受信日時の古い順）。"""
    token = get_access_token(graph_config)
    folder_id = _resolve_folder_id(token, folder_name)
    since_iso = since.strftime("%Y-%m-%dT%H:%M:%SZ")
    resp = requests.get(
        f"{_GRAPH_BASE}/me/mailFolders/{folder_id}/messages",
        headers={"Authorization": f"Bearer {token}",
                 "Prefer": 'outlook.body-content-type="text"'},
        params={"$top": 200, "$orderby": "receivedDateTime asc",
                "$select": "id,subject,receivedDateTime,body",
                "$filter": f"receivedDateTime gt {since_iso}"},
        timeout=30,
    )
    if resp.status_code != 200:
        raise RuntimeError(
            f"メール一覧の取得に失敗しました ({resp.status_code}): {resp.text[:200]}")

    messages = []
    for item in resp.json().get("value", []):
        if item["id"] in exclude_ids:
            continue
        if subject_filter and subject_filter not in item.get("subject", ""):
            continue
        messages.append({
            "id": item["id"],
            "subject": item.get("subject", ""),
            "body_text": item.get("body", {}).get("content", ""),
            "received_at": _parse_graph_datetime(item["receivedDateTime"]),
        })
    return messages


def commit_rows(session: Session, meeting_id: int, rows: list[AttendanceMailRow],
                selected_member_by_index: dict[int, int]) -> dict:
    """会員が選択されていて、かつ出欠区分を正しく認識できた行だけ出欠に反映し、
    対象メールを処理済みとして記録する。出欠区分が認識できなかった行
    （STATUS_MAPに無い値、status==""）は、会員が選択されていてもスキップする
    （空文字のステータスを業務データに書き込まないため）。
    """
    applied = skipped = 0
    for i, row in enumerate(rows):
        member_id = selected_member_by_index.get(i)
        if member_id is None or not row.status:
            skipped += 1
            continue
        upsert_attendance(
            session, meeting_id, member_id, row.status,
            proxy_title=row.proxy_title, proxy_name=row.proxy_name,
            notes=row.notes)
        session.add(ProcessedAttendanceMail(
            message_id=row.message_id, meeting_id=meeting_id,
            received_at=row.received_at))
        upsert_alias(session, row.org_name_raw, member_id)
        applied += 1
    session.commit()
    return {"applied": applied, "skipped": skipped}
