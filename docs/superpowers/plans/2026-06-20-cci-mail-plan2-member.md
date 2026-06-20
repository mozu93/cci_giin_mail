# cci-mail Plan 2: 名簿管理

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 会員名簿のCRUD・変更履歴記録・Excel/CSVインポートを実装し、名簿管理タブを完成させる。

**Architecture:** `member_service.py` でDB操作をカプセル化。`import_service.py` でExcel/CSV → Member変換。UI層（`member_tab.py`）からサービスを呼び出す。変更時は `MemberHistory` に変更前スナップショット（JSON）を保存。

**Tech Stack:** Python 3.11+, PyQt6, SQLAlchemy 2.x, openpyxl, pytest

## Global Constraints

- Plan 1が完了していること（DBモデル・接続・設定が動作する状態）
- テストはインメモリSQLite（conftest.pyのdb_sessionフィクスチャ）を使用
- 変更前スナップショットはJSONで `members` 全フィールド＋ `email_addresses` 配列を含む
- 差し込みデータのCSV突合キーは `member_number`（会員番号）

---

## ファイル構成（新規作成・変更）

```
app/
  services/
    member_service.py      # 新規作成
    import_service.py      # 新規作成
  ui/
    member_tab.py          # Plan 1のプレースホルダーを置き換え
    dialogs/
      member_edit_dialog.py    # 新規作成
      member_history_dialog.py # 新規作成
      import_dialog.py         # 新規作成
tests/
  test_member_service.py   # 新規作成
  test_import_service.py   # 新規作成
```

---

## Task 1: member_service.py

**Files:**
- Create: `app/services/member_service.py`
- Create: `tests/test_member_service.py`

**Interfaces:**
- Consumes: `Member`, `EmailAddress`, `MemberHistory`, `Position`（models.py）、`Session`
- Produces:
  - `create_member(session, member_number, organization_name, name, **kwargs) -> Member`
  - `update_member(session, member_id, changed_by, change_reason, **kwargs) -> Member`
  - `delete_member(session, member_id) -> None`
  - `get_member(session, member_id) -> Member | None`
  - `get_members(session, position_id=None, keyword=None, active_only=True) -> list[Member]`
  - `get_member_history(session, member_id) -> list[MemberHistory]`
  - `set_email_addresses(session, member_id, addresses: list[dict]) -> None`
  - `member_to_snapshot(member: Member) -> str`  ← JSON文字列

- [ ] **Step 1: テストを書く**

```python
# tests/test_member_service.py
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
```

- [ ] **Step 2: テスト実行 → 失敗確認**

```bash
pytest tests/test_member_service.py -v
```

期待: `ImportError`

- [ ] **Step 3: member_service.py を作成**

```python
# app/services/member_service.py
import json
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.database.models import Member, EmailAddress, MemberHistory


def member_to_snapshot(member: Member) -> str:
    data = {
        "member_number":    member.member_number,
        "position_id":      member.position_id,
        "organization_name": member.organization_name,
        "organization_kana": member.organization_kana,
        "title":            member.title,
        "name":             member.name,
        "name_kana":        member.name_kana,
        "notes":            member.notes,
        "is_active":        member.is_active,
        "email_addresses":  [
            {"address": e.address, "label": e.label, "sort_order": e.sort_order}
            for e in member.email_addresses
        ],
    }
    return json.dumps(data, ensure_ascii=False)


def create_member(session: Session, member_number: str,
                  organization_name: str, name: str, **kwargs) -> Member:
    member = Member(
        member_number=member_number,
        organization_name=organization_name,
        name=name,
        **kwargs
    )
    session.add(member)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise
    return member


def get_member(session: Session, member_id: int) -> Member | None:
    return session.get(Member, member_id)


def get_members(session: Session, position_id: int | None = None,
                keyword: str | None = None,
                active_only: bool = True) -> list[Member]:
    q = session.query(Member)
    if active_only:
        q = q.filter(Member.is_active == True)
    if position_id is not None:
        q = q.filter(Member.position_id == position_id)
    if keyword:
        like = f"%{keyword}%"
        q = q.filter(
            Member.organization_name.like(like) |
            Member.name.like(like) |
            Member.member_number.like(like)
        )
    return q.order_by(Member.member_number).all()


def set_email_addresses(session: Session, member_id: int,
                        addresses: list[dict]) -> None:
    if len(addresses) > 5:
        raise ValueError("メールアドレスは最大5件まで登録できます")
    session.query(EmailAddress).filter_by(member_id=member_id).delete()
    for addr in addresses:
        session.add(EmailAddress(
            member_id=member_id,
            address=addr["address"],
            label=addr.get("label", ""),
            sort_order=addr.get("sort_order", 1),
        ))
    session.flush()


def update_member(session: Session, member_id: int,
                  changed_by: str, change_reason: str, **kwargs) -> Member:
    member = session.get(Member, member_id)
    if member is None:
        raise ValueError(f"会員ID {member_id} が見つかりません")
    snapshot = member_to_snapshot(member)
    history = MemberHistory(
        member_id=member_id,
        changed_by=changed_by,
        change_reason=change_reason,
        snapshot=snapshot,
    )
    session.add(history)
    for key, value in kwargs.items():
        setattr(member, key, value)
    session.commit()
    return member


def delete_member(session: Session, member_id: int) -> None:
    member = session.get(Member, member_id)
    if member:
        session.delete(member)
        session.commit()


def get_member_history(session: Session, member_id: int) -> list[MemberHistory]:
    return (session.query(MemberHistory)
            .filter_by(member_id=member_id)
            .order_by(MemberHistory.changed_at.desc())
            .all())
```

- [ ] **Step 4: テスト実行 → パス確認**

```bash
pytest tests/test_member_service.py -v
```

期待: `10 passed`

- [ ] **Step 5: コミット**

```bash
git add app/services/member_service.py tests/test_member_service.py
git commit -m "feat: 会員名簿サービス（CRUD・変更履歴・メールアドレス管理）を追加"
```

---

## Task 2: import_service.py

**Files:**
- Create: `app/services/import_service.py`
- Create: `tests/test_import_service.py`

**Interfaces:**
- Consumes: `create_member()`, `set_email_addresses()`, `get_member`（member_service.py）
- Produces:
  - `load_member_file(filepath: str) -> tuple[list[str], list[list]]`  ← (headers, rows)
  - `import_members(session, rows: list[list], column_map: dict, changed_by: str) -> dict`
    - `column_map`: `{"member_number": 0, "organization_name": 1, ...}` （列インデックスのマッピング）
    - 戻り値: `{"created": int, "updated": int, "errors": list[str]}`

- [ ] **Step 1: テスト用サンプルExcelを生成するfixtureを追加（conftest.py に追記）**

```python
# tests/conftest.py に追記
import openpyxl
import pytest


@pytest.fixture
def sample_excel(tmp_path):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["会員番号", "事業所名", "事業所名フリガナ", "役職名", "氏名", "氏名フリガナ",
                "会議所役職", "メール1", "ラベル1", "メール2", "ラベル2"])
    ws.append(["A-001", "○○商事", "マルマルショウジ", "代表取締役", "山田 太郎",
                "ヤマダ タロウ", "議員", "yamada@example.com", "本人", "", ""])
    ws.append(["A-002", "△△産業", "サンカクサンギョウ", "社長", "鈴木 花子",
                "スズキ ハナコ", "議員", "suzuki@example.com", "本人",
                "somu@example.com", "総務"])
    path = tmp_path / "members.xlsx"
    wb.save(path)
    return str(path)
```

- [ ] **Step 2: テストを書く**

```python
# tests/test_import_service.py
from app.services.import_service import load_member_file, import_members


COLUMN_MAP = {
    "member_number":    0,
    "organization_name": 1,
    "organization_kana": 2,
    "title":            3,
    "name":             4,
    "name_kana":        5,
    "email_1_address":  7,
    "email_1_label":    8,
    "email_2_address":  9,
    "email_2_label":    10,
}


def test_load_member_file_returns_headers_and_rows(sample_excel):
    headers, rows = load_member_file(sample_excel)
    assert len(headers) == 11
    assert headers[0] == "会員番号"
    assert len(rows) == 2


def test_import_members_creates_new(db_session, sample_excel):
    _, rows = load_member_file(sample_excel)
    result = import_members(db_session, rows, COLUMN_MAP, changed_by="管理者")
    assert result["created"] == 2
    assert result["updated"] == 0
    assert result["errors"] == []


def test_import_members_updates_existing(db_session, sample_excel):
    _, rows = load_member_file(sample_excel)
    import_members(db_session, rows, COLUMN_MAP, changed_by="管理者")
    # 2回目は同じ会員番号なのでupdateになる
    result = import_members(db_session, rows, COLUMN_MAP, changed_by="管理者")
    assert result["created"] == 0
    assert result["updated"] == 2


def test_import_members_sets_email_addresses(db_session, sample_excel):
    from app.services.member_service import get_members
    _, rows = load_member_file(sample_excel)
    import_members(db_session, rows, COLUMN_MAP, changed_by="管理者")
    members = get_members(db_session)
    suzuki = next(m for m in members if m.member_number == "A-002")
    assert len(suzuki.email_addresses) == 2
```

- [ ] **Step 3: テスト実行 → 失敗確認**

```bash
pytest tests/test_import_service.py -v
```

期待: `ImportError`

- [ ] **Step 4: import_service.py を作成**

```python
# app/services/import_service.py
from pathlib import Path
from sqlalchemy.orm import Session
from app.services.member_service import (
    create_member, update_member, set_email_addresses, get_members
)


def load_member_file(filepath: str) -> tuple[list[str], list[list]]:
    ext = Path(filepath).suffix.lower()
    if ext in (".xlsx", ".xls"):
        import openpyxl
        wb = openpyxl.load_workbook(filepath, read_only=True, data_only=True)
        ws = wb.active
        rows = list(ws.iter_rows(values_only=True))
        wb.close()
    elif ext == ".csv":
        import csv
        with open(filepath, encoding="utf-8-sig", newline="") as f:
            reader = csv.reader(f)
            rows = [list(r) for r in reader]
    else:
        raise ValueError(f"非対応のファイル形式: {ext}")
    if not rows:
        return [], []
    headers = [str(h) if h is not None else "" for h in rows[0]]
    data_rows = [list(r) for r in rows[1:] if any(c for c in r)]
    return headers, data_rows


def import_members(session: Session, rows: list[list],
                   column_map: dict, changed_by: str) -> dict:
    existing = {m.member_number: m for m in get_members(session, active_only=False)}
    created = updated = 0
    errors: list[str] = []

    def _cell(row, key):
        idx = column_map.get(key)
        if idx is None or idx >= len(row):
            return ""
        val = row[idx]
        return str(val).strip() if val is not None else ""

    for i, row in enumerate(rows, start=2):
        member_number = _cell(row, "member_number")
        if not member_number:
            errors.append(f"行{i}: 会員番号が空です")
            continue
        organization_name = _cell(row, "organization_name")
        name = _cell(row, "name")
        if not organization_name or not name:
            errors.append(f"行{i} ({member_number}): 事業所名または氏名が空です")
            continue

        kwargs = {
            "organization_kana": _cell(row, "organization_kana"),
            "title":             _cell(row, "title"),
            "name_kana":         _cell(row, "name_kana"),
        }

        addresses = []
        for n in range(1, 6):
            addr = _cell(row, f"email_{n}_address")
            if addr:
                addresses.append({
                    "address":    addr,
                    "label":      _cell(row, f"email_{n}_label"),
                    "sort_order": n,
                })

        try:
            if member_number in existing:
                update_member(session, existing[member_number].id,
                              changed_by=changed_by,
                              change_reason="Excelインポートによる更新",
                              organization_name=organization_name,
                              name=name, **kwargs)
                if addresses:
                    set_email_addresses(session,
                                        existing[member_number].id, addresses)
                    session.commit()
                updated += 1
            else:
                m = create_member(session, member_number,
                                  organization_name, name, **kwargs)
                if addresses:
                    set_email_addresses(session, m.id, addresses)
                    session.commit()
                created += 1
        except Exception as e:
            errors.append(f"行{i} ({member_number}): {e}")

    return {"created": created, "updated": updated, "errors": errors}
```

- [ ] **Step 5: テスト実行 → パス確認**

```bash
pytest tests/test_import_service.py -v
```

期待: `4 passed`

- [ ] **Step 6: コミット**

```bash
git add app/services/import_service.py tests/test_import_service.py tests/conftest.py
git commit -m "feat: Excel/CSVインポートサービスを追加"
```

---

## Task 3: 会員編集ダイアログ

**Files:**
- Create: `app/ui/dialogs/member_edit_dialog.py`

**Interfaces:**
- Consumes: `create_member()`, `update_member()`, `set_email_addresses()`, `get_members`（member_service.py）、`Position`（models.py）
- Produces: `MemberEditDialog(session, member=None, staff_name="") -> QDialog`
  - `member=None` のとき新規作成モード
  - `exec()` 後、`result()` が `Accepted` なら保存済み

- [ ] **Step 1: member_edit_dialog.py を作成**

```python
# app/ui/dialogs/member_edit_dialog.py
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QHBoxLayout,
    QLineEdit, QComboBox, QPushButton, QGroupBox,
    QScrollArea, QWidget, QLabel, QMessageBox
)
from PyQt6.QtCore import Qt
from sqlalchemy.orm import Session
from app.database.models import Member, Position
from app.services.member_service import (
    create_member, update_member, set_email_addresses
)

_MAX_EMAILS = 5


class MemberEditDialog(QDialog):
    def __init__(self, session: Session, member: Member | None = None,
                 staff_name: str = "", parent=None):
        super().__init__(parent)
        self._session = session
        self._member = member
        self._staff_name = staff_name
        self.setWindowTitle("会員編集" if member else "会員追加")
        self.setMinimumWidth(520)
        self._build()
        if member:
            self._load(member)

    def _build(self):
        layout = QVBoxLayout(self)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        form_layout = QVBoxLayout(inner)

        # 基本情報
        grp_basic = QGroupBox("基本情報")
        form = QFormLayout(grp_basic)
        self._member_number = QLineEdit()
        self._org_name = QLineEdit()
        self._org_kana = QLineEdit()
        self._title = QLineEdit()
        self._name = QLineEdit()
        self._name_kana = QLineEdit()
        self._position_combo = QComboBox()
        self._notes = QLineEdit()

        self._positions = self._session.query(Position).order_by(Position.sort_order).all()
        self._position_combo.addItem("（なし）", None)
        for p in self._positions:
            self._position_combo.addItem(p.name, p.id)

        form.addRow("会員番号 *", self._member_number)
        form.addRow("会議所役職", self._position_combo)
        form.addRow("事業所名 *", self._org_name)
        form.addRow("事業所名フリガナ", self._org_kana)
        form.addRow("役職名", self._title)
        form.addRow("氏名 *", self._name)
        form.addRow("氏名フリガナ", self._name_kana)
        form.addRow("備考", self._notes)
        form_layout.addWidget(grp_basic)

        # メールアドレス
        grp_email = QGroupBox("メールアドレス（最大5件）")
        email_layout = QFormLayout(grp_email)
        self._email_rows: list[tuple[QLineEdit, QLineEdit]] = []
        for i in range(1, _MAX_EMAILS + 1):
            addr = QLineEdit()
            addr.setPlaceholderText(f"アドレス{i}")
            label = QLineEdit()
            label.setPlaceholderText("ラベル（本人・総務等）")
            row_widget = QHBoxLayout()
            row_widget.addWidget(addr, 3)
            row_widget.addWidget(label, 1)
            container = QWidget()
            container.setLayout(row_widget)
            email_layout.addRow(f"メール{i}", container)
            self._email_rows.append((addr, label))
        form_layout.addWidget(grp_email)

        # 変更理由（編集時のみ表示）
        self._reason_widget = QGroupBox("変更理由")
        reason_form = QFormLayout(self._reason_widget)
        self._change_reason = QLineEdit()
        self._change_reason.setPlaceholderText("変更理由を入力してください（必須）")
        reason_form.addRow("理由", self._change_reason)
        form_layout.addWidget(self._reason_widget)
        if not self._member:
            self._reason_widget.setVisible(False)

        scroll.setWidget(inner)
        layout.addWidget(scroll)

        # ボタン
        btn_row = QHBoxLayout()
        btn_cancel = QPushButton("キャンセル")
        btn_cancel.clicked.connect(self.reject)
        btn_save = QPushButton("保存")
        btn_save.setDefault(True)
        btn_save.clicked.connect(self._save)
        btn_row.addWidget(btn_cancel)
        btn_row.addStretch()
        btn_row.addWidget(btn_save)
        layout.addLayout(btn_row)

    def _load(self, member: Member):
        self._member_number.setText(member.member_number)
        self._member_number.setReadOnly(True)
        self._org_name.setText(member.organization_name)
        self._org_kana.setText(member.organization_kana or "")
        self._title.setText(member.title or "")
        self._name.setText(member.name)
        self._name_kana.setText(member.name_kana or "")
        self._notes.setText(member.notes or "")
        for i, p in enumerate(self._positions):
            if p.id == member.position_id:
                self._position_combo.setCurrentIndex(i + 1)
                break
        for i, ea in enumerate(member.email_addresses[:_MAX_EMAILS]):
            self._email_rows[i][0].setText(ea.address)
            self._email_rows[i][1].setText(ea.label or "")

    def _save(self):
        member_number = self._member_number.text().strip()
        org_name = self._org_name.text().strip()
        name = self._name.text().strip()
        if not member_number or not org_name or not name:
            QMessageBox.warning(self, "入力エラー",
                                "会員番号・事業所名・氏名は必須です。")
            return
        if self._member and not self._change_reason.text().strip():
            QMessageBox.warning(self, "入力エラー", "変更理由を入力してください。")
            return

        position_id = self._position_combo.currentData()
        addresses = []
        for i, (addr_w, label_w) in enumerate(self._email_rows, start=1):
            addr = addr_w.text().strip()
            if addr:
                addresses.append({
                    "address":    addr,
                    "label":      label_w.text().strip(),
                    "sort_order": i,
                })

        try:
            if self._member:
                update_member(
                    self._session, self._member.id,
                    changed_by=self._staff_name,
                    change_reason=self._change_reason.text().strip(),
                    organization_name=org_name,
                    organization_kana=self._org_kana.text().strip(),
                    title=self._title.text().strip(),
                    name=name,
                    name_kana=self._name_kana.text().strip(),
                    notes=self._notes.text().strip(),
                    position_id=position_id,
                )
                set_email_addresses(self._session, self._member.id, addresses)
                self._session.commit()
            else:
                m = create_member(
                    self._session, member_number, org_name, name,
                    organization_kana=self._org_kana.text().strip(),
                    title=self._title.text().strip(),
                    name_kana=self._name_kana.text().strip(),
                    notes=self._notes.text().strip(),
                    position_id=position_id,
                )
                set_email_addresses(self._session, m.id, addresses)
                self._session.commit()
        except Exception as e:
            QMessageBox.critical(self, "エラー", str(e))
            return
        self.accept()
```

- [ ] **Step 2: コミット**

```bash
git add app/ui/dialogs/member_edit_dialog.py
git commit -m "feat: 会員編集ダイアログ（新規・編集・変更理由）を追加"
```

---

## Task 4: 変更履歴ダイアログ

**Files:**
- Create: `app/ui/dialogs/member_history_dialog.py`

**Interfaces:**
- Consumes: `get_member_history()`（member_service.py）
- Produces: `MemberHistoryDialog(session, member_id: int) -> QDialog`

- [ ] **Step 1: member_history_dialog.py を作成**

```python
# app/ui/dialogs/member_history_dialog.py
import json
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QPushButton, QTextEdit, QSplitter, QLabel
)
from PyQt6.QtCore import Qt
from sqlalchemy.orm import Session
from app.services.member_service import get_member_history, get_member


class MemberHistoryDialog(QDialog):
    def __init__(self, session: Session, member_id: int, parent=None):
        super().__init__(parent)
        self._session = session
        self._member_id = member_id
        member = get_member(session, member_id)
        self.setWindowTitle(f"変更履歴: {member.organization_name if member else ''}")
        self.resize(700, 500)
        self._build()
        self._load()

    def _build(self):
        layout = QVBoxLayout(self)
        splitter = QSplitter(Qt.Orientation.Vertical)

        self._table = QTableWidget(0, 3)
        self._table.setHorizontalHeaderLabels(["変更日時", "変更者", "変更理由"])
        self._table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.Stretch)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.currentRowChanged.connect(self._show_snapshot)
        splitter.addWidget(self._table)

        self._snapshot_view = QTextEdit()
        self._snapshot_view.setReadOnly(True)
        self._snapshot_view.setPlaceholderText("行を選択すると変更前のデータを表示します")
        splitter.addWidget(self._snapshot_view)

        layout.addWidget(splitter)

        btn_close = QPushButton("閉じる")
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close)

    def _load(self):
        self._history = get_member_history(self._session, self._member_id)
        self._table.setRowCount(0)
        for h in self._history:
            row = self._table.rowCount()
            self._table.insertRow(row)
            self._table.setItem(row, 0, QTableWidgetItem(
                h.changed_at.strftime("%Y/%m/%d %H:%M")))
            self._table.setItem(row, 1, QTableWidgetItem(h.changed_by))
            self._table.setItem(row, 2, QTableWidgetItem(h.change_reason))

    def _show_snapshot(self, row: int):
        if row < 0 or row >= len(self._history):
            return
        snap = self._history[row].snapshot
        try:
            data = json.loads(snap)
            lines = [f"{k}: {v}" for k, v in data.items() if k != "email_addresses"]
            emails = data.get("email_addresses", [])
            for i, e in enumerate(emails, 1):
                lines.append(f"メール{i}: {e['address']} ({e['label']})")
            self._snapshot_view.setPlainText("\n".join(lines))
        except Exception:
            self._snapshot_view.setPlainText(snap)
```

- [ ] **Step 2: コミット**

```bash
git add app/ui/dialogs/member_history_dialog.py
git commit -m "feat: 変更履歴ダイアログを追加"
```

---

## Task 5: インポートダイアログ

**Files:**
- Create: `app/ui/dialogs/import_dialog.py`

**Interfaces:**
- Consumes: `load_member_file()`, `import_members()`（import_service.py）
- Produces: `ImportDialog(session, staff_name: str) -> QDialog`

- [ ] **Step 1: import_dialog.py を作成**

```python
# app/ui/dialogs/import_dialog.py
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QComboBox, QFileDialog, QMessageBox, QGroupBox, QFormLayout
)
from sqlalchemy.orm import Session
from app.services.import_service import load_member_file, import_members

_MEMBER_FIELDS = [
    ("member_number",    "会員番号 *"),
    ("organization_name","事業所名 *"),
    ("organization_kana","事業所名フリガナ"),
    ("title",            "役職名"),
    ("name",             "氏名 *"),
    ("name_kana",        "氏名フリガナ"),
    ("email_1_address",  "メール1 アドレス"),
    ("email_1_label",    "メール1 ラベル"),
    ("email_2_address",  "メール2 アドレス"),
    ("email_2_label",    "メール2 ラベル"),
    ("email_3_address",  "メール3 アドレス"),
    ("email_3_label",    "メール3 ラベル"),
    ("email_4_address",  "メール4 アドレス"),
    ("email_4_label",    "メール4 ラベル"),
    ("email_5_address",  "メール5 アドレス"),
    ("email_5_label",    "メール5 ラベル"),
]


class ImportDialog(QDialog):
    def __init__(self, session: Session, staff_name: str = "", parent=None):
        super().__init__(parent)
        self._session = session
        self._staff_name = staff_name
        self._headers: list[str] = []
        self._rows: list[list] = []
        self.setWindowTitle("会員名簿インポート")
        self.setMinimumWidth(600)
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)

        # ファイル選択
        file_row = QHBoxLayout()
        self._file_path = QLineEdit()
        self._file_path.setReadOnly(True)
        btn_browse = QPushButton("ファイル選択")
        btn_browse.clicked.connect(self._browse)
        file_row.addWidget(QLabel("ファイル:"))
        file_row.addWidget(self._file_path, 1)
        file_row.addWidget(btn_browse)
        layout.addLayout(file_row)

        # 列マッピング
        grp = QGroupBox("列マッピング（ファイル読み込み後に設定）")
        form = QFormLayout(grp)
        self._combos: dict[str, QComboBox] = {}
        for field_key, field_label in _MEMBER_FIELDS:
            combo = QComboBox()
            combo.addItem("（使用しない）", None)
            self._combos[field_key] = combo
            form.addRow(field_label, combo)
        layout.addWidget(grp)

        # ボタン
        btn_row = QHBoxLayout()
        btn_cancel = QPushButton("キャンセル")
        btn_cancel.clicked.connect(self.reject)
        self._btn_import = QPushButton("インポート実行")
        self._btn_import.setEnabled(False)
        self._btn_import.clicked.connect(self._run_import)
        btn_row.addWidget(btn_cancel)
        btn_row.addStretch()
        btn_row.addWidget(self._btn_import)
        layout.addLayout(btn_row)

    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "ファイルを選択", "",
            "Excel/CSV (*.xlsx *.xls *.csv)")
        if not path:
            return
        try:
            headers, rows = load_member_file(path)
        except Exception as e:
            QMessageBox.critical(self, "エラー", str(e))
            return
        self._file_path.setText(path)
        self._headers = headers
        self._rows = rows
        self._populate_combos(headers)
        self._btn_import.setEnabled(True)

    def _populate_combos(self, headers: list[str]):
        for combo in self._combos.values():
            combo.clear()
            combo.addItem("（使用しない）", None)
            for i, h in enumerate(headers):
                combo.addItem(h, i)
        # ヘッダー名で自動マッピング
        auto_map = {
            "会員番号": "member_number",
            "事業所名": "organization_name",
            "事業所名フリガナ": "organization_kana",
            "役職名": "title",
            "氏名": "name",
            "氏名フリガナ": "name_kana",
        }
        for i, h in enumerate(headers):
            if h in auto_map:
                field_key = auto_map[h]
                if field_key in self._combos:
                    self._combos[field_key].setCurrentIndex(i + 1)

    def _run_import(self):
        column_map = {}
        for field_key, combo in self._combos.items():
            idx = combo.currentData()
            if idx is not None:
                column_map[field_key] = idx
        if "member_number" not in column_map:
            QMessageBox.warning(self, "エラー", "「会員番号」列のマッピングは必須です。")
            return
        result = import_members(self._session, self._rows, column_map,
                                changed_by=self._staff_name or "インポート")
        msg = (f"インポート完了\n\n"
               f"新規登録: {result['created']} 件\n"
               f"更新: {result['updated']} 件\n")
        if result["errors"]:
            msg += f"\nエラー ({len(result['errors'])} 件):\n"
            msg += "\n".join(result["errors"][:10])
            if len(result["errors"]) > 10:
                msg += f"\n... 他 {len(result['errors']) - 10} 件"
        QMessageBox.information(self, "完了", msg)
        self.accept()
```

- [ ] **Step 2: コミット**

```bash
git add app/ui/dialogs/import_dialog.py
git commit -m "feat: 会員インポートダイアログ（列マッピング付き）を追加"
```

---

## Task 6: 名簿管理タブ（member_tab.py）

**Files:**
- Modify: `app/ui/member_tab.py`（Plan 1のプレースホルダーを置き換え）

**Interfaces:**
- Consumes: `get_members()`, `delete_member()`（member_service.py）、`MemberEditDialog`、`MemberHistoryDialog`、`ImportDialog`

- [ ] **Step 1: member_tab.py を実装**

```python
# app/ui/member_tab.py
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLineEdit, QComboBox, QLabel, QHeaderView,
    QMessageBox
)
from PyQt6.QtCore import Qt
from app.database.connection import get_session
from app.database.models import Position
from app.services.member_service import get_members, delete_member


class MemberTab(QWidget):
    def __init__(self):
        super().__init__()
        self._staff_name = ""
        self._build()
        self._load()

    def set_staff_name(self, name: str):
        self._staff_name = name

    def _build(self):
        layout = QVBoxLayout(self)

        # ツールバー
        toolbar = QHBoxLayout()
        self._search = QLineEdit()
        self._search.setPlaceholderText("キーワード検索（事業所名・氏名・会員番号）")
        self._search.textChanged.connect(self._load)
        self._pos_filter = QComboBox()
        self._pos_filter.addItem("すべての役職", None)
        self._pos_filter.currentIndexChanged.connect(self._load)
        btn_add = QPushButton("追加")
        btn_add.clicked.connect(self._add)
        btn_edit = QPushButton("編集")
        btn_edit.clicked.connect(self._edit)
        btn_delete = QPushButton("削除")
        btn_delete.clicked.connect(self._delete)
        btn_history = QPushButton("変更履歴")
        btn_history.clicked.connect(self._show_history)
        btn_import = QPushButton("インポート")
        btn_import.clicked.connect(self._import)
        toolbar.addWidget(self._search, 2)
        toolbar.addWidget(QLabel("役職:"))
        toolbar.addWidget(self._pos_filter)
        toolbar.addStretch()
        toolbar.addWidget(btn_add)
        toolbar.addWidget(btn_edit)
        toolbar.addWidget(btn_delete)
        toolbar.addWidget(btn_history)
        toolbar.addWidget(btn_import)
        layout.addLayout(toolbar)

        # 一覧テーブル
        self._table = QTableWidget(0, 6)
        self._table.setHorizontalHeaderLabels(
            ["会員番号", "会議所役職", "事業所名", "氏名", "役職名", "メール件数"])
        self._table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.Stretch)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.doubleClicked.connect(self._edit)
        layout.addWidget(self._table)

        self._count_label = QLabel("")
        layout.addWidget(self._count_label)

    def _load_positions(self):
        session = get_session()
        try:
            positions = session.query(Position).order_by(Position.sort_order).all()
            current = self._pos_filter.currentData()
            self._pos_filter.blockSignals(True)
            self._pos_filter.clear()
            self._pos_filter.addItem("すべての役職", None)
            for p in positions:
                self._pos_filter.addItem(p.name, p.id)
            self._pos_filter.blockSignals(False)
            if current is not None:
                for i in range(self._pos_filter.count()):
                    if self._pos_filter.itemData(i) == current:
                        self._pos_filter.setCurrentIndex(i)
                        break
        finally:
            session.close()

    def _load(self):
        self._load_positions()
        session = get_session()
        try:
            members = get_members(
                session,
                position_id=self._pos_filter.currentData(),
                keyword=self._search.text().strip() or None,
            )
            self._members = members
            self._table.setRowCount(0)
            for m in members:
                row = self._table.rowCount()
                self._table.insertRow(row)
                self._table.setItem(row, 0, QTableWidgetItem(m.member_number))
                pos_name = m.position.name if m.position else ""
                self._table.setItem(row, 1, QTableWidgetItem(pos_name))
                self._table.setItem(row, 2, QTableWidgetItem(m.organization_name))
                self._table.setItem(row, 3, QTableWidgetItem(m.name))
                self._table.setItem(row, 4, QTableWidgetItem(m.title or ""))
                self._table.setItem(row, 5, QTableWidgetItem(
                    str(len(m.email_addresses))))
                self._table.item(row, 0).setData(
                    Qt.ItemDataRole.UserRole, m.id)
            self._count_label.setText(f"{len(members)} 件")
        finally:
            session.close()

    def _selected_member_id(self) -> int | None:
        row = self._table.currentRow()
        if row < 0:
            return None
        item = self._table.item(row, 0)
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def _add(self):
        from app.ui.dialogs.member_edit_dialog import MemberEditDialog
        session = get_session()
        dlg = MemberEditDialog(session, staff_name=self._staff_name, parent=self)
        if dlg.exec():
            self._load()
        session.close()

    def _edit(self):
        member_id = self._selected_member_id()
        if member_id is None:
            return
        from app.ui.dialogs.member_edit_dialog import MemberEditDialog
        from app.services.member_service import get_member
        session = get_session()
        member = get_member(session, member_id)
        dlg = MemberEditDialog(session, member=member,
                               staff_name=self._staff_name, parent=self)
        if dlg.exec():
            self._load()
        session.close()

    def _delete(self):
        member_id = self._selected_member_id()
        if member_id is None:
            return
        ret = QMessageBox.question(
            self, "削除確認",
            "この会員を削除しますか？\n関連する変更履歴もすべて削除されます。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if ret != QMessageBox.StandardButton.Yes:
            return
        session = get_session()
        delete_member(session, member_id)
        session.close()
        self._load()

    def _show_history(self):
        member_id = self._selected_member_id()
        if member_id is None:
            return
        from app.ui.dialogs.member_history_dialog import MemberHistoryDialog
        session = get_session()
        dlg = MemberHistoryDialog(session, member_id, parent=self)
        dlg.exec()
        session.close()

    def _import(self):
        from app.ui.dialogs.import_dialog import ImportDialog
        session = get_session()
        dlg = ImportDialog(session, staff_name=self._staff_name, parent=self)
        if dlg.exec():
            self._load()
        session.close()
```

- [ ] **Step 2: 全テスト確認**

```bash
pytest tests/ -v
```

期待: `9 passed` 以上（全テストがパス）

- [ ] **Step 3: コミット**

```bash
git add app/ui/member_tab.py
git commit -m "feat: 名簿管理タブ（検索・CRUD・変更履歴・インポート）を実装 — Plan 2完了"
```

---

## Plan 2 完了チェックリスト

- [ ] `pytest tests/ -v` で全テストがパス
- [ ] `python main.py` → 名簿管理タブで会員を追加できる
- [ ] 会員編集時に変更理由を入力しないと保存できない
- [ ] 変更履歴ボタンで変更前データが表示される
- [ ] Excelファイルをインポートして会員が登録される
- [ ] 役職フィルタ・キーワード検索が機能する
