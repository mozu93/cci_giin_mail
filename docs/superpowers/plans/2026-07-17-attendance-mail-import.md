# 常議員会 出欠メール取り込み Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Microsoft Graph API経由で担当者のOutlookから常議員会の出欠連絡メール（【出欠】【事業所名】等の括弧ラベル形式）を読み取り、事前入力タブで選択中の会議の出欠（`AttendanceRecord`）へプレビュー確認のうえ反映できるようにする。

**Architecture:** 新規サービスモジュール`app/services/attendance_mail_service.py`に「解析（純粋関数）→会員突合→プレビュー生成→確定処理」を実装し、新規ダイアログ`AttendanceMailImportDialog`（`merge_preview_dialog.py`と同型のプレビュー→確定パターン）から呼び出す。取り込み済み判定は新規テーブル`ProcessedAttendanceMail`にメッセージIDを記録する方式とし、共有DB（PostgreSQLモード時は全端末で共有）に依存させることで複数職員・複数PCでの重複取り込みを防ぐ。

**Tech Stack:** Python 3.11 / PyQt6 / SQLAlchemy / pytest + pytest-qt / MSAL（既存の`email_service.py`と同じトークンキャッシュ）/ Microsoft Graph API v1.0

## Global Constraints

- 対象は常議員会の出欠連絡メールのみ。委員会（総務・地域経済・中小小規模企業）の出欠連絡はフォーマット未確定のためスコープ外。
- 会員突合は事業所名のみで行う（メールアドレス等は使わない）。0件/複数件一致は自動確定せず「未選択」として扱う。
- 出欠区分は `出席`→`出席`、`出席(※代理)`→`代理`、`委任`→`委任`、`欠席`→`欠席` の4パターンのみ対応する。
- 処理済みメールの判定はメールボックス側の状態（フォルダ移動・既読等）を使わず、アプリの共有DBに記録する。
- バックグラウンド自動巡回は実装しない。手動の「検索」ボタン実行のみ。
- 既存パターンを踏襲する：`_NoWheelComboBox`（`app/ui/meeting_widgets/reception_widget.py`）、`merge_preview_dialog.py`のプレビュー→確定フロー、`_migrate_sqlite`/`_migrate_postgresql`のカラム追加パターン。

参照spec: `docs/superpowers/specs/2026-07-17-attendance-mail-import-design.md`

---

## File Structure

- **Modify:** `app/database/models.py` — `AttendanceRecord.notes`列追加、新規`ProcessedAttendanceMail`モデル追加
- **Modify:** `app/database/connection.py` — `_migrate_sqlite`/`_migrate_postgresql`に`notes`列追加処理を追加
- **Modify:** `app/services/meeting_service.py` — `upsert_attendance`に`notes`引数追加
- **Modify:** `app/services/email_service.py` — MSALスコープに`Mail.Read`追加
- **Create:** `app/services/attendance_mail_service.py` — メール解析・会員突合・プレビュー生成・確定処理
- **Modify:** `app/utils/app_config.py` — 取り込みフォルダ名・対象件名の前回値保存/取得
- **Create:** `app/ui/dialogs/attendance_mail_import_dialog.py` — プレビュー→確定ダイアログ
- **Modify:** `app/ui/meeting_widgets/preentry_widget.py` — 「メールから出欠を取り込む」ボタン追加
- **Test:** `tests/test_meeting_service.py`（既存、notesケース追加）
- **Test:** `tests/test_migration_attendance_notes.py`（新規）
- **Test:** `tests/test_attendance_mail_service.py`（新規）
- **Test:** `tests/test_attendance_mail_import_dialog.py`（新規）

---

### Task 1: `AttendanceRecord.notes`列の追加とマイグレーション

**Files:**
- Modify: `app/database/models.py:187-199`（`AttendanceRecord`クラス）
- Modify: `app/database/connection.py:38-45`（`_migrate_sqlite`）、`app/database/connection.py:96-115`（`_migrate_postgresql`）
- Modify: `app/services/meeting_service.py:31-44`（`upsert_attendance`）
- Test: `tests/test_meeting_service.py`（新規ファイル。既存に無いため今回新規作成）
- Test: `tests/test_migration_attendance_notes.py`

**Interfaces:**
- Produces: `AttendanceRecord.notes: str`（デフォルト`""`）、`upsert_attendance(session, meeting_id, member_id, status, proxy_title="", proxy_name="", notes="") -> AttendanceRecord`

- [ ] **Step 1: Write the failing test for `upsert_attendance`の`notes`引数**

`tests/test_meeting_service.py`を新規作成：

```python
from app.services.meeting_service import create_meeting, upsert_attendance
from app.services.member_service import create_member
from datetime import date


def test_upsert_attendance_saves_notes(db_session):
    member = create_member(db_session, "A-001", "○○商事", "山田太郎")
    meeting = create_meeting(db_session, "常議員会", date(2026, 7, 20))

    record = upsert_attendance(
        db_session, meeting.id, member.id, "出席", notes="体調不良のため途中退席予定")

    assert record.notes == "体調不良のため途中退席予定"


def test_upsert_attendance_notes_defaults_to_empty(db_session):
    member = create_member(db_session, "A-002", "△△産業", "鈴木花子")
    meeting = create_meeting(db_session, "常議員会", date(2026, 7, 20))

    record = upsert_attendance(db_session, meeting.id, member.id, "欠席")

    assert record.notes == ""
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_meeting_service.py -v`
Expected: FAIL — `TypeError: upsert_attendance() got an unexpected keyword argument 'notes'`

- [ ] **Step 3: `AttendanceRecord`に`notes`列を追加**

`app/database/models.py`の`AttendanceRecord`クラス（199行目付近、`proxy_name = Column(String, default="")`の直後）に追加：

```python
    proxy_name = Column(String, default="")
    notes = Column(Text, default="")
```

- [ ] **Step 4: `upsert_attendance`に`notes`引数を追加**

`app/services/meeting_service.py`の`upsert_attendance`を以下に置き換え：

```python
def upsert_attendance(session: Session, meeting_id: int, member_id: int,
                      status: str, proxy_title: str = "",
                      proxy_name: str = "", notes: str = "") -> AttendanceRecord:
    r = (session.query(AttendanceRecord)
         .filter_by(meeting_id=meeting_id, member_id=member_id)
         .first())
    if r is None:
        r = AttendanceRecord(meeting_id=meeting_id, member_id=member_id)
        session.add(r)
    r.status = status
    r.proxy_title = proxy_title
    r.proxy_name = proxy_name
    r.notes = notes
    session.commit()
    return r
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_meeting_service.py -v`
Expected: PASS（2 passed）

- [ ] **Step 6: マイグレーションの失敗テストを書く**

`tests/test_migration_attendance_notes.py`を新規作成：

```python
import sqlite3
from sqlalchemy import create_engine, text
from app.database.connection import _migrate_sqlite
from app.database.models import Base


def test_migrate_sqlite_adds_notes_column(tmp_path):
    db_path = tmp_path / "old_schema.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "CREATE TABLE attendance_records (id INTEGER PRIMARY KEY, "
        "meeting_id INTEGER NOT NULL, member_id INTEGER NOT NULL, "
        "status TEXT NOT NULL, actual_status TEXT, "
        "proxy_title TEXT, proxy_name TEXT)")
    conn.commit()
    conn.close()

    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    _migrate_sqlite(engine)
    _migrate_sqlite(engine)  # 2回目もエラーにならないこと

    with engine.connect() as conn:
        cols = [row[1] for row in conn.execute(text("PRAGMA table_info(attendance_records)"))]
    assert cols.count("notes") == 1
    assert "notes" in cols
```

- [ ] **Step 7: Run test to verify it fails**

Run: `pytest tests/test_migration_attendance_notes.py -v`
Expected: FAIL — `assert "notes" in cols` で失敗（列が存在しない）

- [ ] **Step 8: `_migrate_sqlite`と`_migrate_postgresql`に列追加処理を実装**

`app/database/connection.py`の`_migrate_sqlite`関数内、`attendance_cols`のブロック（41-45行目）を以下に置き換え：

```python
        attendance_cols = {
            row[1] for row in conn.execute(text("PRAGMA table_info(attendance_records)"))
        }
        if "actual_status" not in attendance_cols:
            conn.execute(text(
                "ALTER TABLE attendance_records ADD COLUMN actual_status TEXT DEFAULT ''"
            ))
            conn.commit()
        if "notes" not in attendance_cols:
            conn.execute(text(
                "ALTER TABLE attendance_records ADD COLUMN notes TEXT DEFAULT ''"
            ))
            conn.commit()
```

`app/database/connection.py`の`_migrate_postgresql`関数内、末尾（116行目の直後）に追加：

```python
        attendance_cols = {col["name"] for col in insp.get_columns("attendance_records")}
        if "notes" not in attendance_cols:
            conn.execute(text("ALTER TABLE attendance_records ADD COLUMN notes TEXT DEFAULT ''"))
```

- [ ] **Step 9: Run test to verify it passes**

Run: `pytest tests/test_migration_attendance_notes.py -v`
Expected: PASS（1 passed）

- [ ] **Step 10: Commit**

```bash
git add app/database/models.py app/database/connection.py app/services/meeting_service.py tests/test_meeting_service.py tests/test_migration_attendance_notes.py
git commit -m "feat: AttendanceRecordに備考(notes)列を追加する"
```

---

### Task 2: メール本文の解析（純粋関数、DB・ネットワーク不使用）

**Files:**
- Create: `app/services/attendance_mail_service.py`
- Test: `tests/test_attendance_mail_service.py`

**Interfaces:**
- Consumes: なし（純粋関数のみ）
- Produces: `STATUS_MAP: dict[str, str]`、`parse_body(body_text: str) -> dict`（キー: `status_raw`, `org_name`, `name`, `proxy_title`, `proxy_name`, `notes`、すべて`str`）、`normalize_org_name(name: str) -> str`

- [ ] **Step 1: Write the failing tests**

`tests/test_attendance_mail_service.py`を新規作成：

```python
from app.services.attendance_mail_service import parse_body, normalize_org_name, STATUS_MAP

_SAMPLE_BODY = """
【出　　欠】出席(※代理)

【事業所名】　スーパーサンシ株式会社

【氏　　名】代表取締役　高倉　護

【代理者名】別所　喜三生

【代理役職】監査役

【受任者名（委任代理人）】

【備考】
"""

_SAMPLE_BODY_ATTEND = """
【出　　欠】出席

【事業所名】三重相互（株）

【氏　　名】議員　三重太郎

【代理者名】

【代理役職】

【受任者名（委任代理人）】

【備考】来月から担当者が変わります
"""


def test_parse_body_extracts_proxy_fields():
    fields = parse_body(_SAMPLE_BODY)
    assert fields["status_raw"] == "出席(※代理)"
    assert fields["org_name"] == "スーパーサンシ株式会社"
    assert fields["name"] == "代表取締役　高倉　護"
    assert fields["proxy_title"] == "監査役"
    assert fields["proxy_name"] == "別所　喜三生"
    assert fields["notes"] == ""


def test_parse_body_extracts_notes():
    fields = parse_body(_SAMPLE_BODY_ATTEND)
    assert fields["status_raw"] == "出席"
    assert fields["org_name"] == "三重相互（株）"
    assert fields["proxy_title"] == ""
    assert fields["proxy_name"] == ""
    assert fields["notes"] == "来月から担当者が変わります"


def test_status_map_covers_four_patterns():
    assert STATUS_MAP["出席"] == "出席"
    assert STATUS_MAP["出席(※代理)"] == "代理"
    assert STATUS_MAP["委任"] == "委任"
    assert STATUS_MAP["欠席"] == "欠席"


def test_normalize_org_name_strips_company_suffixes_and_spaces():
    assert normalize_org_name("スーパーサンシ株式会社") == normalize_org_name("スーパーサンシ")
    assert normalize_org_name("三重相互（株）") == normalize_org_name("三重相互(株)")
    assert normalize_org_name("三重 相互") == normalize_org_name("三重相互")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_attendance_mail_service.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.attendance_mail_service'`

- [ ] **Step 3: `app/services/attendance_mail_service.py`を新規作成**

```python
import re

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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_attendance_mail_service.py -v`
Expected: PASS（4 passed）

- [ ] **Step 5: Commit**

```bash
git add app/services/attendance_mail_service.py tests/test_attendance_mail_service.py
git commit -m "feat: 出欠メール本文の括弧ラベル解析を追加する"
```

---

### Task 3: 会員突合（`match_member`）と`ProcessedAttendanceMail`モデル

**Files:**
- Modify: `app/database/models.py`（末尾に`ProcessedAttendanceMail`追加）
- Modify: `app/services/attendance_mail_service.py`
- Test: `tests/test_attendance_mail_service.py`（追記）

**Interfaces:**
- Consumes: `normalize_org_name(name: str) -> str`（Task 2で定義済み）
- Produces: `match_member(session: Session, org_name_raw: str) -> Member | None`、モデル`ProcessedAttendanceMail(id, message_id: str, meeting_id: int | None, processed_at: datetime)`

- [ ] **Step 1: Write the failing tests**

`tests/test_attendance_mail_service.py`に追記：

```python
from app.services.attendance_mail_service import match_member
from app.services.member_service import create_member


def test_match_member_unique_match(db_session):
    create_member(db_session, "A-001", "○○商事", "山田太郎")
    m = match_member(db_session, "○○商事")
    assert m is not None
    assert m.member_number == "A-001"


def test_match_member_normalizes_company_suffix(db_session):
    create_member(db_session, "A-001", "スーパーサンシ株式会社", "高倉護")
    m = match_member(db_session, "スーパーサンシ（株）")
    assert m is not None
    assert m.member_number == "A-001"


def test_match_member_returns_none_when_no_match(db_session):
    create_member(db_session, "A-001", "○○商事", "山田太郎")
    assert match_member(db_session, "存在しない会社") is None


def test_match_member_returns_none_when_ambiguous(db_session):
    create_member(db_session, "A-001", "山田商事", "山田太郎")
    create_member(db_session, "A-002", "山田商事", "山田次郎")
    assert match_member(db_session, "山田商事") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_attendance_mail_service.py -v -k match_member`
Expected: FAIL — `ImportError: cannot import name 'match_member'`

- [ ] **Step 3: `ProcessedAttendanceMail`モデルを追加**

`app/database/models.py`の末尾（`AttendanceRecord`クラスの直後、200行目付近）に追加：

```python
class ProcessedAttendanceMail(Base):
    __tablename__ = "processed_attendance_mails"
    id = Column(Integer, primary_key=True)
    message_id = Column(String, unique=True, nullable=False)
    meeting_id = Column(Integer, ForeignKey("meetings.id"), nullable=True)
    processed_at = Column(DateTime, nullable=False, default=datetime.now)
```

- [ ] **Step 4: `match_member`を実装**

`app/services/attendance_mail_service.py`の先頭のimportを以下に変更：

```python
import re
from sqlalchemy.orm import Session
from app.database.models import Member
```

ファイル末尾に追加：

```python
def match_member(session: Session, org_name_raw: str) -> Member | None:
    """事業所名を正規化して一意に一致する会員を返す。0件/複数件一致はNone。"""
    target = normalize_org_name(org_name_raw)
    members = session.query(Member).filter(Member.is_active == True).all()
    matches = [m for m in members if normalize_org_name(m.organization_name) == target]
    if len(matches) == 1:
        return matches[0]
    return None
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_attendance_mail_service.py -v`
Expected: PASS（全件）

- [ ] **Step 6: Commit**

```bash
git add app/database/models.py app/services/attendance_mail_service.py tests/test_attendance_mail_service.py
git commit -m "feat: 出欠メールの事業所名から会員を突合する処理を追加する"
```

---

### Task 4: プレビュー生成（`AttendanceMailRow` / `build_preview`）

**Files:**
- Modify: `app/services/attendance_mail_service.py`
- Test: `tests/test_attendance_mail_service.py`（追記）

**Interfaces:**
- Consumes: `parse_body`, `STATUS_MAP`, `normalize_org_name`, `match_member`（Task 2, 3）、`app.database.models.AttendanceRecord`
- Produces: `@dataclass AttendanceMailRow(message_id: str, org_name_raw: str, name_raw: str, status: str, proxy_title: str, proxy_name: str, notes: str, matched_member: Member | None, existing_status: str | None)`、`build_preview(session: Session, meeting_id: int, messages: list[dict]) -> list[AttendanceMailRow]`（`messages`の各要素は`{"id": str, "body_text": str}`を含むdict、Task 5で定義する`fetch_messages`の戻り値形式）

- [ ] **Step 1: Write the failing tests**

`tests/test_attendance_mail_service.py`に追記：

```python
from datetime import date
from app.services.attendance_mail_service import build_preview
from app.services.meeting_service import create_meeting, upsert_attendance

_BODY_TEMPLATE = """
【出　　欠】{status}

【事業所名】{org}

【氏　　名】{name}

【代理者名】{proxy_name}

【代理役職】{proxy_title}

【受任者名（委任代理人）】

【備考】{notes}
"""


def _body(status="出席", org="○○商事", name="山田太郎",
          proxy_name="", proxy_title="", notes=""):
    return _BODY_TEMPLATE.format(
        status=status, org=org, name=name,
        proxy_name=proxy_name, proxy_title=proxy_title, notes=notes)


def test_build_preview_matches_member_and_status(db_session):
    create_member_org = "○○商事"
    from app.services.member_service import create_member
    create_member(db_session, "A-001", create_member_org, "山田太郎")
    meeting = create_meeting(db_session, "常議員会", date(2026, 7, 20))

    messages = [{"id": "msg-1", "body_text": _body(status="出席(※代理)",
                                                    proxy_name="別所喜三生",
                                                    proxy_title="監査役")}]
    rows = build_preview(db_session, meeting.id, messages)

    assert len(rows) == 1
    row = rows[0]
    assert row.status == "代理"
    assert row.proxy_name == "別所喜三生"
    assert row.proxy_title == "監査役"
    assert row.matched_member is not None
    assert row.matched_member.member_number == "A-001"
    assert row.existing_status is None


def test_build_preview_shows_existing_status_when_already_recorded(db_session):
    from app.services.member_service import create_member
    member = create_member(db_session, "A-001", "○○商事", "山田太郎")
    meeting = create_meeting(db_session, "常議員会", date(2026, 7, 20))
    upsert_attendance(db_session, meeting.id, member.id, "出席")

    messages = [{"id": "msg-2", "body_text": _body(status="欠席")}]
    rows = build_preview(db_session, meeting.id, messages)

    assert rows[0].existing_status == "出席"
    assert rows[0].status == "欠席"


def test_build_preview_keeps_only_latest_message_per_organization(db_session):
    from app.services.member_service import create_member
    create_member(db_session, "A-001", "○○商事", "山田太郎")
    meeting = create_meeting(db_session, "常議員会", date(2026, 7, 20))

    # fetch_messagesは受信日時の古い順に返す契約 → 後勝ちで最新のみ残る
    messages = [
        {"id": "msg-old", "body_text": _body(status="出席")},
        {"id": "msg-new", "body_text": _body(status="欠席")},
    ]
    rows = build_preview(db_session, meeting.id, messages)

    assert len(rows) == 1
    assert rows[0].message_id == "msg-new"
    assert rows[0].status == "欠席"


def test_build_preview_unmatched_organization_has_no_member(db_session):
    meeting = create_meeting(db_session, "常議員会", date(2026, 7, 20))
    messages = [{"id": "msg-3", "body_text": _body(org="存在しない会社")}]
    rows = build_preview(db_session, meeting.id, messages)

    assert rows[0].matched_member is None
    assert rows[0].existing_status is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_attendance_mail_service.py -v -k build_preview`
Expected: FAIL — `ImportError: cannot import name 'build_preview'`

- [ ] **Step 3: `AttendanceMailRow`と`build_preview`を実装**

`app/services/attendance_mail_service.py`の先頭importを以下に変更：

```python
import re
from dataclasses import dataclass
from sqlalchemy.orm import Session
from app.database.models import Member, AttendanceRecord
```

ファイル末尾に追加：

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_attendance_mail_service.py -v`
Expected: PASS（全件）

- [ ] **Step 5: Commit**

```bash
git add app/services/attendance_mail_service.py tests/test_attendance_mail_service.py
git commit -m "feat: 出欠メールのプレビュー生成(重複排除・既存登録表示)を追加する"
```

---

### Task 5: Graph APIからのメール取得（`fetch_messages`）とMSALスコープ更新

**Files:**
- Modify: `app/services/email_service.py:10`
- Modify: `app/services/attendance_mail_service.py`
- Test: `tests/test_attendance_mail_service.py`（追記）

**Interfaces:**
- Consumes: `app.services.email_service.get_access_token(graph_config: dict) -> str`（既存）
- Produces: `fetch_messages(graph_config: dict, folder_name: str, subject_filter: str, exclude_ids: set[str]) -> list[dict]`（各要素`{"id": str, "subject": str, "body_text": str}`、受信日時の古い順）。フォルダが見つからない場合は`ValueError`、HTTPエラー時は`RuntimeError`を送出する。

- [ ] **Step 1: Write the failing tests**

`tests/test_attendance_mail_service.py`に追記：

```python
import pytest
from app.services.attendance_mail_service import fetch_messages


class _FakeResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload
        self.text = str(payload)

    def json(self):
        return self._payload


def test_fetch_messages_resolves_folder_and_filters(monkeypatch):
    monkeypatch.setattr(
        "app.services.attendance_mail_service.get_access_token",
        lambda cfg: "dummy-token")

    def fake_get(url, headers=None, params=None, timeout=None):
        if url.endswith("/me/mailFolders"):
            assert params["$filter"] == "displayName eq '常議員会出欠'"
            return _FakeResponse(200, {"value": [{"id": "folder-1"}]})
        if url.endswith("/me/mailFolders/folder-1/messages"):
            return _FakeResponse(200, {"value": [
                {"id": "msg-1", "subject": "常議員会出欠連絡",
                 "receivedDateTime": "2026-07-15T10:00:00Z",
                 "body": {"content": "本文1"}},
                {"id": "msg-2", "subject": "別件のお知らせ",
                 "receivedDateTime": "2026-07-16T10:00:00Z",
                 "body": {"content": "本文2"}},
            ]})
        raise AssertionError(f"unexpected url: {url}")

    monkeypatch.setattr("app.services.attendance_mail_service.requests.get", fake_get)

    messages = fetch_messages({}, "常議員会出欠", "出欠連絡", exclude_ids=set())

    assert len(messages) == 1
    assert messages[0]["id"] == "msg-1"
    assert messages[0]["body_text"] == "本文1"


def test_fetch_messages_excludes_already_processed(monkeypatch):
    monkeypatch.setattr(
        "app.services.attendance_mail_service.get_access_token",
        lambda cfg: "dummy-token")

    def fake_get(url, headers=None, params=None, timeout=None):
        if url.endswith("/me/mailFolders"):
            return _FakeResponse(200, {"value": [{"id": "folder-1"}]})
        return _FakeResponse(200, {"value": [
            {"id": "msg-1", "subject": "件名",
             "receivedDateTime": "2026-07-15T10:00:00Z",
             "body": {"content": "本文1"}},
        ]})

    monkeypatch.setattr("app.services.attendance_mail_service.requests.get", fake_get)

    messages = fetch_messages({}, "常議員会出欠", "", exclude_ids={"msg-1"})

    assert messages == []


def test_fetch_messages_raises_when_folder_not_found(monkeypatch):
    monkeypatch.setattr(
        "app.services.attendance_mail_service.get_access_token",
        lambda cfg: "dummy-token")

    def fake_get(url, headers=None, params=None, timeout=None):
        return _FakeResponse(200, {"value": []})

    monkeypatch.setattr("app.services.attendance_mail_service.requests.get", fake_get)

    with pytest.raises(ValueError, match="見つかりません"):
        fetch_messages({}, "存在しないフォルダ", "", exclude_ids=set())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_attendance_mail_service.py -v -k fetch_messages`
Expected: FAIL — `ImportError: cannot import name 'fetch_messages'`

- [ ] **Step 3: `email_service.py`のスコープを更新**

`app/services/email_service.py:10`を以下に置き換え：

```python
_SCOPES = ["https://graph.microsoft.com/Mail.Send",
           "https://graph.microsoft.com/Mail.Read"]
```

- [ ] **Step 4: `fetch_messages`を実装**

`app/services/attendance_mail_service.py`の先頭importを以下に変更：

```python
import re
import requests
from dataclasses import dataclass
from sqlalchemy.orm import Session
from app.database.models import Member, AttendanceRecord
from app.services.email_service import get_access_token

_GRAPH_BASE = "https://graph.microsoft.com/v1.0"
```

ファイル末尾に追加：

```python
def _resolve_folder_id(token: str, folder_name: str) -> str:
    resp = requests.get(
        f"{_GRAPH_BASE}/me/mailFolders",
        headers={"Authorization": f"Bearer {token}"},
        params={"$filter": f"displayName eq '{folder_name}'"},
        timeout=30,
    )
    if resp.status_code != 200:
        raise RuntimeError(
            f"フォルダ一覧の取得に失敗しました ({resp.status_code}): {resp.text[:200]}")
    values = resp.json().get("value", [])
    if not values:
        raise ValueError(
            f"フォルダ「{folder_name}」が見つかりません。Outlookのフォルダ名を確認してください。")
    return values[0]["id"]


def fetch_messages(graph_config: dict, folder_name: str, subject_filter: str,
                   exclude_ids: set[str]) -> list[dict]:
    """指定フォルダ内のメールをGraph APIで取得する（受信日時の古い順）。"""
    token = get_access_token(graph_config)
    folder_id = _resolve_folder_id(token, folder_name)
    resp = requests.get(
        f"{_GRAPH_BASE}/me/mailFolders/{folder_id}/messages",
        headers={"Authorization": f"Bearer {token}",
                 "Prefer": 'outlook.body-content-type="text"'},
        params={"$top": 200, "$orderby": "receivedDateTime asc",
                "$select": "id,subject,receivedDateTime,body"},
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
        })
    return messages
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_attendance_mail_service.py -v`
Expected: PASS（全件）

- [ ] **Step 6: 既存のemail_serviceテストが壊れていないことを確認**

Run: `pytest tests/test_email_service.py -v`
Expected: PASS（変更なし、スコープ定数はテスト対象外のため影響なし）

- [ ] **Step 7: Commit**

```bash
git add app/services/email_service.py app/services/attendance_mail_service.py tests/test_attendance_mail_service.py
git commit -m "feat: Graph APIから出欠連絡メールを取得する処理を追加する"
```

---

### Task 6: 確定処理（`commit_rows`）

**Files:**
- Modify: `app/services/attendance_mail_service.py`
- Test: `tests/test_attendance_mail_service.py`（追記）

**Interfaces:**
- Consumes: `AttendanceMailRow`（Task 4）、`app.database.models.ProcessedAttendanceMail`（Task 3）、`app.services.meeting_service.upsert_attendance`（Task 1で`notes`引数追加済み）
- Produces: `commit_rows(session: Session, meeting_id: int, rows: list[AttendanceMailRow], selected_member_by_index: dict[int, int]) -> dict`（戻り値`{"applied": int, "skipped": int}`）。`selected_member_by_index`はプレビュー行のインデックス→確定するmember_idの対応表（未選択の行はキーに含まれない）。

- [ ] **Step 1: Write the failing tests**

`tests/test_attendance_mail_service.py`に追記：

```python
from app.services.attendance_mail_service import commit_rows
from app.database.models import ProcessedAttendanceMail, AttendanceRecord


def test_commit_rows_applies_selected_rows_and_records_message_id(db_session):
    from app.services.member_service import create_member
    member = create_member(db_session, "A-001", "○○商事", "山田太郎")
    meeting = create_meeting(db_session, "常議員会", date(2026, 7, 20))

    messages = [{"id": "msg-1", "body_text": _body(status="出席")}]
    rows = build_preview(db_session, meeting.id, messages)

    result = commit_rows(db_session, meeting.id, rows,
                         selected_member_by_index={0: member.id})

    assert result == {"applied": 1, "skipped": 0}
    record = (db_session.query(AttendanceRecord)
             .filter_by(meeting_id=meeting.id, member_id=member.id).first())
    assert record.status == "出席"
    processed = db_session.query(ProcessedAttendanceMail).all()
    assert len(processed) == 1
    assert processed[0].message_id == "msg-1"


def test_commit_rows_skips_rows_without_selected_member(db_session):
    meeting = create_meeting(db_session, "常議員会", date(2026, 7, 20))
    messages = [{"id": "msg-1", "body_text": _body(org="存在しない会社")}]
    rows = build_preview(db_session, meeting.id, messages)

    result = commit_rows(db_session, meeting.id, rows, selected_member_by_index={})

    assert result == {"applied": 0, "skipped": 1}
    assert db_session.query(ProcessedAttendanceMail).count() == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_attendance_mail_service.py -v -k commit_rows`
Expected: FAIL — `ImportError: cannot import name 'commit_rows'`

- [ ] **Step 3: `commit_rows`を実装**

`app/services/attendance_mail_service.py`の先頭importに`ProcessedAttendanceMail`と`upsert_attendance`を追加：

```python
from app.database.models import Member, AttendanceRecord, ProcessedAttendanceMail
from app.services.meeting_service import upsert_attendance
```

（`from app.services.email_service import get_access_token`はそのまま維持）

ファイル末尾に追加：

```python
def commit_rows(session: Session, meeting_id: int, rows: list[AttendanceMailRow],
                selected_member_by_index: dict[int, int]) -> dict:
    """会員が選択されている行だけ出欠に反映し、対象メールを処理済みとして記録する。"""
    applied = skipped = 0
    for i, row in enumerate(rows):
        member_id = selected_member_by_index.get(i)
        if member_id is None:
            skipped += 1
            continue
        upsert_attendance(
            session, meeting_id, member_id, row.status,
            proxy_title=row.proxy_title, proxy_name=row.proxy_name,
            notes=row.notes)
        session.add(ProcessedAttendanceMail(
            message_id=row.message_id, meeting_id=meeting_id))
        applied += 1
    session.commit()
    return {"applied": applied, "skipped": skipped}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_attendance_mail_service.py -v`
Expected: PASS（全件）

- [ ] **Step 5: Commit**

```bash
git add app/services/attendance_mail_service.py tests/test_attendance_mail_service.py
git commit -m "feat: 出欠メールプレビューの確定処理(commit_rows)を追加する"
```

---

### Task 7: 取り込みフォルダ名・対象件名の前回値を保存する

**Files:**
- Modify: `app/utils/app_config.py`
- Test: `tests/test_app_config_attendance_mail.py`（新規）

**Interfaces:**
- Produces: `get_attendance_mail_folder() -> str`、`save_attendance_mail_folder(folder_name: str) -> None`、`get_attendance_mail_subject_filter() -> str`、`save_attendance_mail_subject_filter(subject_filter: str) -> None`（いずれも端末ローカルの`app_config.json`に保存。フォルダ名はOutlook側の個人設定に紐づくため、`get_html_export_path`のようなPostgreSQL共有設定にはしない）

- [ ] **Step 1: Write the failing test**

`tests/test_app_config_attendance_mail.py`を新規作成：

```python
from app.utils import app_config


def test_save_and_get_attendance_mail_folder(monkeypatch, tmp_path):
    monkeypatch.setattr(app_config, "_config_path", lambda: tmp_path / "app_config.json")

    assert app_config.get_attendance_mail_folder() == ""
    app_config.save_attendance_mail_folder("常議員会出欠")
    assert app_config.get_attendance_mail_folder() == "常議員会出欠"


def test_save_and_get_attendance_mail_subject_filter(monkeypatch, tmp_path):
    monkeypatch.setattr(app_config, "_config_path", lambda: tmp_path / "app_config.json")

    assert app_config.get_attendance_mail_subject_filter() == ""
    app_config.save_attendance_mail_subject_filter("出欠連絡")
    assert app_config.get_attendance_mail_subject_filter() == "出欠連絡"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_app_config_attendance_mail.py -v`
Expected: FAIL — `AttributeError: module 'app.utils.app_config' has no attribute 'get_attendance_mail_folder'`

- [ ] **Step 3: 4関数を実装**

`app/utils/app_config.py`の末尾に追加：

```python
def get_attendance_mail_folder() -> str:
    return get_config().get("attendance_mail_folder", "")


def save_attendance_mail_folder(folder_name: str) -> None:
    config = get_config()
    config["attendance_mail_folder"] = folder_name
    save_config(config)


def get_attendance_mail_subject_filter() -> str:
    return get_config().get("attendance_mail_subject_filter", "")


def save_attendance_mail_subject_filter(subject_filter: str) -> None:
    config = get_config()
    config["attendance_mail_subject_filter"] = subject_filter
    save_config(config)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_app_config_attendance_mail.py -v`
Expected: PASS（2 passed）

- [ ] **Step 5: Commit**

```bash
git add app/utils/app_config.py tests/test_app_config_attendance_mail.py
git commit -m "feat: 出欠メール取り込みのフォルダ名・件名の前回値を保存する"
```

---

### Task 8: プレビューダイアログ（検索・一覧表示）

**Files:**
- Create: `app/ui/dialogs/attendance_mail_import_dialog.py`
- Test: `tests/test_attendance_mail_import_dialog.py`

**Interfaces:**
- Consumes: `attendance_mail_service.fetch_messages`, `build_preview`, `commit_rows`（Task 4-6）、`app_config.get_attendance_mail_folder/save_attendance_mail_folder/get_attendance_mail_subject_filter/save_attendance_mail_subject_filter`（Task 7）、`app.database.connection.get_session`
- Produces: `class AttendanceMailImportDialog(QDialog)`、コンストラクタ`__init__(self, meeting_id: int, graph_config: dict, parent=None)`。内部の`_NoWheelComboBox`（`reception_widget.py`と同じ実装をこのファイル内に複製、既存の重複パターンを踏襲）

- [ ] **Step 1: Write the failing test**

`tests/test_attendance_mail_import_dialog.py`を新規作成：

```python
from datetime import date
from app.services.meeting_service import create_meeting
from app.services.member_service import create_member


def test_search_populates_table_with_matched_member_preselected(
        qtbot, monkeypatch, db_session):
    monkeypatch.setattr(
        "app.ui.dialogs.attendance_mail_import_dialog.get_session",
        lambda: db_session)
    member = create_member(db_session, "A-001", "○○商事", "山田太郎")
    meeting = create_meeting(db_session, "常議員会", date(2026, 7, 20))

    monkeypatch.setattr(
        "app.ui.dialogs.attendance_mail_import_dialog.fetch_messages",
        lambda graph_config, folder, subject, exclude_ids: [
            {"id": "msg-1", "body_text": (
                "【出　　欠】出席\n【事業所名】○○商事\n【氏　　名】山田太郎\n"
                "【代理者名】\n【代理役職】\n【備考】")},
        ])

    from app.ui.dialogs.attendance_mail_import_dialog import AttendanceMailImportDialog
    dlg = AttendanceMailImportDialog(meeting_id=meeting.id, graph_config={})
    qtbot.addWidget(dlg)

    dlg._folder_input.setText("常議員会出欠")
    dlg._search()

    assert dlg._table.rowCount() == 1
    combo = dlg._table.cellWidget(0, dlg._COL_MEMBER)
    assert combo.currentData() == member.id


def test_search_leaves_unmatched_row_unselected(qtbot, monkeypatch, db_session):
    monkeypatch.setattr(
        "app.ui.dialogs.attendance_mail_import_dialog.get_session",
        lambda: db_session)
    meeting = create_meeting(db_session, "常議員会", date(2026, 7, 20))

    monkeypatch.setattr(
        "app.ui.dialogs.attendance_mail_import_dialog.fetch_messages",
        lambda graph_config, folder, subject, exclude_ids: [
            {"id": "msg-1", "body_text": (
                "【出　　欠】出席\n【事業所名】存在しない会社\n【氏　　名】不明\n"
                "【代理者名】\n【代理役職】\n【備考】")},
        ])

    from app.ui.dialogs.attendance_mail_import_dialog import AttendanceMailImportDialog
    dlg = AttendanceMailImportDialog(meeting_id=meeting.id, graph_config={})
    qtbot.addWidget(dlg)
    dlg._search()

    combo = dlg._table.cellWidget(0, dlg._COL_MEMBER)
    assert combo.currentData() is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_attendance_mail_import_dialog.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.ui.dialogs.attendance_mail_import_dialog'`

- [ ] **Step 3: ダイアログを実装**

`app/ui/dialogs/attendance_mail_import_dialog.py`を新規作成：

```python
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit,
    QPushButton, QLabel, QTableWidget, QTableWidgetItem, QHeaderView,
    QComboBox, QMessageBox,
)
from app.database.connection import get_session
from app.services.member_service import get_members
from app.services.attendance_mail_service import fetch_messages, build_preview, commit_rows
from app.utils.app_config import (
    get_attendance_mail_folder, save_attendance_mail_folder,
    get_attendance_mail_subject_filter, save_attendance_mail_subject_filter,
)


class _NoWheelComboBox(QComboBox):
    def wheelEvent(self, event):
        event.ignore()


class AttendanceMailImportDialog(QDialog):
    _COL_ORG = 0
    _COL_NAME = 1
    _COL_STATUS = 2
    _COL_PROXY = 3
    _COL_NOTES = 4
    _COL_EXISTING = 5
    _COL_MEMBER = 6

    def __init__(self, meeting_id: int, graph_config: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("メールから出欠を取り込む")
        self.resize(760, 520)
        self._meeting_id = meeting_id
        self._graph_config = graph_config
        self._rows = []
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            "Outlookで仕分けした対象フォルダから、常議員会の出欠連絡メールを取り込みます。"))

        form = QFormLayout()
        self._folder_input = QLineEdit(get_attendance_mail_folder())
        form.addRow("対象フォルダ名", self._folder_input)
        self._subject_input = QLineEdit(get_attendance_mail_subject_filter())
        form.addRow("対象件名（部分一致・空欄可）", self._subject_input)
        layout.addLayout(form)

        btn_row = QHBoxLayout()
        btn_search = QPushButton("検索")
        btn_search.clicked.connect(self._search)
        btn_row.addWidget(btn_search)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self._table = QTableWidget(0, 7)
        self._table.setHorizontalHeaderLabels([
            "事業所名（メール記載）", "氏名", "出欠", "代理役職・代理者名",
            "備考", "既存の登録", "会員"])
        self._table.horizontalHeader().setSectionResizeMode(
            self._COL_ORG, QHeaderView.ResizeMode.Stretch)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self._table)

        self._status_label = QLabel("（未検索）")
        layout.addWidget(self._status_label)

        btn_close = QHBoxLayout()
        btn_apply = QPushButton("反映")
        btn_apply.clicked.connect(self._apply)
        btn_cancel = QPushButton("キャンセル")
        btn_cancel.clicked.connect(self.reject)
        btn_close.addStretch()
        btn_close.addWidget(btn_cancel)
        btn_close.addWidget(btn_apply)
        layout.addLayout(btn_close)

    def _search(self):
        folder_name = self._folder_input.text().strip()
        if not folder_name:
            QMessageBox.warning(self, "入力エラー", "対象フォルダ名を入力してください。")
            return
        subject_filter = self._subject_input.text().strip()
        save_attendance_mail_folder(folder_name)
        save_attendance_mail_subject_filter(subject_filter)

        session = get_session()
        try:
            from app.database.models import ProcessedAttendanceMail
            processed_ids = {
                r.message_id for r in
                session.query(ProcessedAttendanceMail).all()
            }
            try:
                messages = fetch_messages(
                    self._graph_config, folder_name, subject_filter, processed_ids)
            except (ValueError, RuntimeError) as e:
                QMessageBox.critical(self, "エラー", str(e))
                return
            self._rows = build_preview(session, self._meeting_id, messages)
            members = get_members(session, active_only=True)
        finally:
            session.close()

        self._refresh_table(members)
        self._status_label.setText(f"{len(self._rows)} 件のメールを読み込みました。")

    def _refresh_table(self, members):
        self._table.setRowCount(0)
        for row in self._rows:
            r = self._table.rowCount()
            self._table.insertRow(r)
            self._table.setItem(r, self._COL_ORG, QTableWidgetItem(row.org_name_raw))
            self._table.setItem(r, self._COL_NAME, QTableWidgetItem(row.name_raw))
            self._table.setItem(r, self._COL_STATUS, QTableWidgetItem(row.status))
            proxy_text = (f"{row.proxy_title} {row.proxy_name}".strip()
                         if (row.proxy_title or row.proxy_name) else "")
            self._table.setItem(r, self._COL_PROXY, QTableWidgetItem(proxy_text))
            self._table.setItem(r, self._COL_NOTES, QTableWidgetItem(row.notes))
            existing_text = (f"{row.existing_status} → {row.status}"
                            if row.existing_status and row.existing_status != row.status
                            else (row.existing_status or ""))
            self._table.setItem(r, self._COL_EXISTING, QTableWidgetItem(existing_text))

            combo = _NoWheelComboBox()
            combo.addItem("（会員未選択）", None)
            selected_index = 0
            for i, m in enumerate(members, start=1):
                combo.addItem(f"{m.organization_name}（{m.name}）", m.id)
                if row.matched_member is not None and m.id == row.matched_member.id:
                    selected_index = i
            combo.setCurrentIndex(selected_index)
            if selected_index == 0:
                combo.setStyleSheet("background-color: #FEE2E2;")
            self._table.setCellWidget(r, self._COL_MEMBER, combo)

    def _apply(self):
        selected_member_by_index = {}
        for r in range(self._table.rowCount()):
            combo = self._table.cellWidget(r, self._COL_MEMBER)
            member_id = combo.currentData()
            if member_id is not None:
                selected_member_by_index[r] = member_id

        session = get_session()
        try:
            result = commit_rows(
                session, self._meeting_id, self._rows, selected_member_by_index)
        finally:
            session.close()

        QMessageBox.information(
            self, "取り込み完了",
            f"反映: {result['applied']}件 / 未選択のためスキップ: {result['skipped']}件")
        self.accept()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_attendance_mail_import_dialog.py -v`
Expected: PASS（2 passed）

- [ ] **Step 5: Commit**

```bash
git add app/ui/dialogs/attendance_mail_import_dialog.py tests/test_attendance_mail_import_dialog.py
git commit -m "feat: 出欠メール取り込みのプレビューダイアログを追加する"
```

---

### Task 9: 反映処理のスキップ挙動テストと`_NoWheelComboBox`ホバースクロール確認

**Files:**
- Modify: `tests/test_attendance_mail_import_dialog.py`

**Interfaces:**
- Consumes: `AttendanceMailImportDialog`（Task 8）

- [ ] **Step 1: Write the failing test**

`tests/test_attendance_mail_import_dialog.py`に追記：

```python
from app.database.models import ProcessedAttendanceMail, AttendanceRecord


def test_apply_commits_only_selected_rows(qtbot, monkeypatch, db_session):
    monkeypatch.setattr(
        "app.ui.dialogs.attendance_mail_import_dialog.get_session",
        lambda: db_session)
    member = create_member(db_session, "A-001", "○○商事", "山田太郎")
    meeting = create_meeting(db_session, "常議員会", date(2026, 7, 20))

    monkeypatch.setattr(
        "app.ui.dialogs.attendance_mail_import_dialog.fetch_messages",
        lambda graph_config, folder, subject, exclude_ids: [
            {"id": "msg-1", "body_text": (
                "【出　　欠】出席\n【事業所名】○○商事\n【氏　　名】山田太郎\n"
                "【代理者名】\n【代理役職】\n【備考】")},
            {"id": "msg-2", "body_text": (
                "【出　　欠】欠席\n【事業所名】存在しない会社\n【氏　　名】不明\n"
                "【代理者名】\n【代理役職】\n【備考】")},
        ])

    from app.ui.dialogs.attendance_mail_import_dialog import AttendanceMailImportDialog
    dlg = AttendanceMailImportDialog(meeting_id=meeting.id, graph_config={})
    qtbot.addWidget(dlg)
    dlg._search()

    dlg._apply()

    record = (db_session.query(AttendanceRecord)
             .filter_by(meeting_id=meeting.id, member_id=member.id).first())
    assert record.status == "出席"
    assert db_session.query(ProcessedAttendanceMail).count() == 1
    assert db_session.query(ProcessedAttendanceMail).first().message_id == "msg-1"
```

- [ ] **Step 2: Run test to verify it fails or passes**

Run: `pytest tests/test_attendance_mail_import_dialog.py -v -k test_apply_commits_only_selected_rows`
Expected: このテストはTask 8の実装だけで既にPASSするはずである（`commit_rows`と`_apply`は実装済みのため）。PASSすることを確認する（回帰防止のためのテスト追加）。

- [ ] **Step 3: `_NoWheelComboBox`のホイールイベント無視を確認するテストを追加**

`tests/test_attendance_mail_import_dialog.py`に追記：

```python
from PyQt6.QtCore import QPoint
from PyQt6.QtGui import QWheelEvent
from PyQt6.QtCore import QPointF


def test_no_wheel_combo_ignores_wheel_event(qtbot, monkeypatch, db_session):
    monkeypatch.setattr(
        "app.ui.dialogs.attendance_mail_import_dialog.get_session",
        lambda: db_session)
    member = create_member(db_session, "A-001", "○○商事", "山田太郎")
    meeting = create_meeting(db_session, "常議員会", date(2026, 7, 20))

    monkeypatch.setattr(
        "app.ui.dialogs.attendance_mail_import_dialog.fetch_messages",
        lambda graph_config, folder, subject, exclude_ids: [
            {"id": "msg-1", "body_text": (
                "【出　　欠】出席\n【事業所名】○○商事\n【氏　　名】山田太郎\n"
                "【代理者名】\n【代理役職】\n【備考】")},
        ])

    from app.ui.dialogs.attendance_mail_import_dialog import AttendanceMailImportDialog
    dlg = AttendanceMailImportDialog(meeting_id=meeting.id, graph_config={})
    qtbot.addWidget(dlg)
    dlg._search()

    combo = dlg._table.cellWidget(0, dlg._COL_MEMBER)
    before = combo.currentIndex()
    event = QWheelEvent(
        QPointF(0, 0), QPointF(0, 0), QPoint(0, 120), QPoint(0, 120),
        Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.NoScrollPhase, False)
    combo.wheelEvent(event)
    assert combo.currentIndex() == before
```

`tests/test_attendance_mail_import_dialog.py`の先頭importに`Qt`を追加：

```python
from PyQt6.QtCore import Qt
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_attendance_mail_import_dialog.py -v`
Expected: PASS（全件）

- [ ] **Step 5: Commit**

```bash
git add tests/test_attendance_mail_import_dialog.py
git commit -m "test: 反映のスキップ挙動とコンボのホイール無視を検証するテストを追加する"
```

---

### Task 10: 「事前入力」タブへのボタン追加

**Files:**
- Modify: `app/ui/meeting_widgets/preentry_widget.py`
- Test: `tests/test_preentry_attendance_mail_button.py`（新規）

**Interfaces:**
- Consumes: `AttendanceMailImportDialog`（Task 8）、既存の`PreentryWidget.__init__(readonly)`, `PreentryWidget.load(meeting_id)`, `PreentryWidget._load_preentry()`

- [ ] **Step 1: Write the failing test**

`tests/test_preentry_attendance_mail_button.py`を新規作成：

```python
from datetime import date
from app.services.meeting_service import create_meeting


def test_mail_import_button_hidden_when_readonly(qtbot, db_session, monkeypatch):
    monkeypatch.setattr(
        "app.ui.meeting_widgets.preentry_widget.get_session", lambda: db_session)
    from app.ui.meeting_widgets.preentry_widget import PreentryWidget
    w = PreentryWidget(readonly=True)
    qtbot.addWidget(w)
    assert w._btn_mail_import is None


def test_mail_import_button_opens_dialog_and_refreshes(qtbot, db_session, monkeypatch):
    monkeypatch.setattr(
        "app.ui.meeting_widgets.preentry_widget.get_session", lambda: db_session)
    meeting = create_meeting(db_session, "常議員会", date(2026, 7, 20))

    from app.ui.meeting_widgets import preentry_widget as mod

    class _FakeDialog:
        def __init__(self, meeting_id, graph_config, parent=None):
            _FakeDialog.created_with = meeting_id
        def exec(self):
            return 1  # QDialog.DialogCode.Accepted相当

    monkeypatch.setattr(mod, "AttendanceMailImportDialog", _FakeDialog)

    w = mod.PreentryWidget(readonly=False)
    qtbot.addWidget(w)
    w.load(meeting.id)

    reload_called = []
    monkeypatch.setattr(w, "_load_preentry", lambda: reload_called.append(True))

    w._btn_mail_import.click()

    assert _FakeDialog.created_with == meeting.id
    assert reload_called == [True]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_preentry_attendance_mail_button.py -v`
Expected: FAIL — `AttributeError: 'PreentryWidget' object has no attribute '_btn_mail_import'`

- [ ] **Step 3: ボタンを追加**

`app/ui/meeting_widgets/preentry_widget.py`の先頭importに追加：

```python
from app.ui.dialogs.attendance_mail_import_dialog import AttendanceMailImportDialog
from app.utils.app_config import get_graph_config
```

`_build`メソッド内、`if not self._readonly:` ブロック（`btn_reset`を追加している箇所）を以下に置き換え：

```python
        btn_row = QHBoxLayout()
        self._btn_mail_import = None
        if not self._readonly:
            btn_reset = QPushButton("並び替え解除")
            btn_reset.clicked.connect(self._reset_sort)
            btn_row.addWidget(btn_reset)
            self._btn_mail_import = QPushButton("メールから出欠を取り込む")
            self._btn_mail_import.clicked.connect(self._open_mail_import)
            btn_row.addWidget(self._btn_mail_import)
```

クラス内（`load`メソッドの直後）にメソッドを追加：

```python
    def _open_mail_import(self):
        if self._meeting_id is None:
            return
        dlg = AttendanceMailImportDialog(
            meeting_id=self._meeting_id, graph_config=get_graph_config(), parent=self)
        if dlg.exec():
            self._load_preentry()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_preentry_attendance_mail_button.py -v`
Expected: PASS（2 passed）

- [ ] **Step 5: Run full test suite**

Run: `pytest -q`
Expected: 全件PASS（既存テストを含む）

- [ ] **Step 6: Commit**

```bash
git add app/ui/meeting_widgets/preentry_widget.py tests/test_preentry_attendance_mail_button.py
git commit -m "feat: 事前入力タブにメールから出欠を取り込むボタンを追加する"
```

---

## Self-Review Notes

- **Spec coverage:** `notes`列追加(Task 1)、括弧ラベル解析(Task 2)、会員突合・正規化(Task 3)、重複排除・既存登録表示(Task 4)、Graph API取得・スコープ追加(Task 5)、確定処理・処理済み記録(Task 6)、フォルダ名/件名の前回値保存(Task 7)、プレビューダイアログ(Task 8-9)、事前入力タブへの導線(Task 10) — spec全項目に対応済み。委員会分はスコープ外として明記済み。
- **Type consistency:** `AttendanceMailRow`のフィールド名・`build_preview`/`commit_rows`のシグネチャはTask 4で定義したものをTask 6, 8, 9で一貫して使用している。`selected_member_by_index`（インデックスキー）という名称・型をTask 6-8間で統一した。
- **確認済み:** `get_graph_config()`は`app/utils/app_config.py:55`に既存関数として実在することを確認済み（`get_config().get("graph", {})`を返す）。Task 10で新規importとして問題なく使える。
