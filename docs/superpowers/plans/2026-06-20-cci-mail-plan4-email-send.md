# cci-mail Plan 4: メール送信（Graph API・送信フロー）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Microsoft Graph API でのメール送信・差し込み展開・個別添付ファイルマッチング・送信フロー5ステップのUIを実装し、メール送信タブを完成させる。

**Architecture:** `email_service.py` でGraph APIを使ったメール送信をカプセル化。`send_job_service.py` でジョブ・ログのDB操作を管理。`send_tab.py` はステップウィジェットを縦に並べた1タブUI。差し込み展開は `email_service.py` 内の `render_body()` で行う。

**Tech Stack:** Python 3.11+, PyQt6, SQLAlchemy 2.x, msal, requests, pytest

## Global Constraints

- Plan 1〜3が完了していること
- テストはインメモリSQLite（conftest.pyのdb_sessionフィクスチャ）を使用
- Graph APIの送信エンドポイント: `https://graph.microsoft.com/v1.0/users/{from_address}/sendMail`
- 添付ファイルはBase64エンコードして `attachments` 配列に含める
- 差し込みキー: `{事業所名}` `{役職名}` `{氏名}` `{会議所役職名}` `{col1}`〜`{col5}`
- 送信ループは1件ずつ順次処理し、エラーはスキップして次の件へ
- `{col1}`〜`{col5}` が未設定の場合は空文字で展開する

---

## ファイル構成（新規作成・変更）

```
app/
  services/
    email_service.py          # 新規作成
    send_job_service.py       # 新規作成
  ui/
    send_tab.py               # Plan 1プレースホルダーを置き換え
    dialogs/
      merge_preview_dialog.py  # 新規作成
      attach_confirm_dialog.py # 新規作成
tests/
  test_email_service.py
  test_send_job_service.py
```

---

## Task 1: email_service.py（差し込み展開 + Graph API送信）

**Files:**
- Create: `app/services/email_service.py`
- Create: `tests/test_email_service.py`

**Interfaces:**
- Produces:
  - `render_body(template: str, context: dict) -> str`
  - `build_message(to_address, subject, body, attachments: list[str]) -> dict`  ← Graph API用JSONペイロード
  - `get_access_token(graph_config: dict) -> str`
  - `send_mail(graph_config: dict, to_address: str, subject: str, body: str, attachments: list[str] = []) -> None`
  - `send_test_mail(graph_config: dict, subject: str, body: str) -> None`

- [ ] **Step 1: テストを書く（差し込み展開のみ、API呼び出しは除外）**

```python
# tests/test_email_service.py
import pytest
from app.services.email_service import render_body, build_message


def test_render_body_basic():
    template = "こんにちは、{事業所名}の{氏名}様。"
    context = {"事業所名": "○○商事", "氏名": "山田 太郎"}
    result = render_body(template, context)
    assert result == "こんにちは、○○商事の山田 太郎様。"


def test_render_body_col_placeholders():
    template = "案件: {col1}、金額: {col2}"
    context = {"col1": "総会", "col2": "5,000円", "col3": "", "col4": "", "col5": ""}
    result = render_body(template, context)
    assert result == "案件: 総会、金額: 5,000円"


def test_render_body_missing_key_becomes_empty():
    template = "こんにちは {氏名}様。{col1}"
    context = {"氏名": "山田 太郎"}
    result = render_body(template, context)
    assert "{col1}" not in result
    assert "山田 太郎" in result


def test_render_body_all_placeholders():
    template = "{事業所名} {役職名} {氏名} {会議所役職名} {col1} {col2} {col3} {col4} {col5}"
    context = {
        "事業所名": "A社", "役職名": "社長", "氏名": "田中",
        "会議所役職名": "議員", "col1": "1", "col2": "2",
        "col3": "3", "col4": "4", "col5": "5",
    }
    result = render_body(template, context)
    assert result == "A社 社長 田中 議員 1 2 3 4 5"


def test_build_message_structure():
    msg = build_message(
        to_address="test@example.com",
        subject="テスト",
        body="本文テスト",
        attachments=[],
    )
    assert msg["message"]["toRecipients"][0]["emailAddress"]["address"] == "test@example.com"
    assert msg["message"]["subject"] == "テスト"
    assert msg["message"]["body"]["content"] == "本文テスト"
    assert msg["message"]["attachments"] == []


def test_build_message_with_attachment(tmp_path):
    f = tmp_path / "test.txt"
    f.write_text("hello", encoding="utf-8")
    msg = build_message("to@example.com", "件名", "本文", [str(f)])
    attachments = msg["message"]["attachments"]
    assert len(attachments) == 1
    assert attachments[0]["name"] == "test.txt"
    assert attachments[0]["@odata.type"] == "#microsoft.graph.fileAttachment"
```

- [ ] **Step 2: テスト実行 → 失敗確認**

```bash
pytest tests/test_email_service.py -v
```

期待: `ImportError`

- [ ] **Step 3: email_service.py を作成**

```python
# app/services/email_service.py
import base64
import os
import re
import requests
import msal

_ALL_KEYS = ["事業所名", "役職名", "氏名", "会議所役職名",
             "col1", "col2", "col3", "col4", "col5"]


def render_body(template: str, context: dict) -> str:
    for key in _ALL_KEYS:
        placeholder = f"{{{key}}}"
        value = str(context.get(key, ""))
        template = template.replace(placeholder, value)
    return template


def build_message(to_address: str, subject: str, body: str,
                  attachments: list[str]) -> dict:
    attachment_list = []
    for path in attachments:
        if not os.path.exists(path):
            continue
        with open(path, "rb") as f:
            content = base64.b64encode(f.read()).decode("utf-8")
        attachment_list.append({
            "@odata.type":  "#microsoft.graph.fileAttachment",
            "name":         os.path.basename(path),
            "contentBytes": content,
        })
    return {
        "message": {
            "subject": subject,
            "body": {
                "contentType": "Text",
                "content":     body,
            },
            "toRecipients": [
                {"emailAddress": {"address": to_address}}
            ],
            "attachments": attachment_list,
        },
        "saveToSentItems": "true",
    }


def get_access_token(graph_config: dict) -> str:
    app = msal.ConfidentialClientApplication(
        graph_config["client_id"],
        authority=f"https://login.microsoftonline.com/{graph_config['tenant_id']}",
        client_credential=graph_config["client_secret"],
    )
    result = app.acquire_token_for_client(
        scopes=["https://graph.microsoft.com/.default"]
    )
    if "access_token" not in result:
        raise RuntimeError(
            f"トークン取得失敗: {result.get('error_description', str(result))}"
        )
    return result["access_token"]


def send_mail(graph_config: dict, to_address: str, subject: str,
              body: str, attachments: list[str] | None = None) -> None:
    token = get_access_token(graph_config)
    from_address = graph_config["from_address"]
    payload = build_message(to_address, subject, body, attachments or [])
    url = f"https://graph.microsoft.com/v1.0/users/{from_address}/sendMail"
    resp = requests.post(
        url,
        headers={"Authorization": f"Bearer {token}",
                 "Content-Type": "application/json"},
        json=payload,
        timeout=30,
    )
    if resp.status_code not in (200, 202):
        raise RuntimeError(
            f"送信失敗 ({resp.status_code}): {resp.text[:200]}"
        )


def send_test_mail(graph_config: dict, subject: str, body: str) -> None:
    test_address = graph_config.get("test_address", "")
    if not test_address:
        raise ValueError("テスト送信先アドレスが設定されていません。")
    send_mail(graph_config, test_address, f"【テスト】{subject}", body)
```

- [ ] **Step 4: テスト実行 → パス確認**

```bash
pytest tests/test_email_service.py -v
```

期待: `6 passed`

- [ ] **Step 5: コミット**

```bash
git add app/services/email_service.py tests/test_email_service.py
git commit -m "feat: Graph APIメール送信サービス（差し込み展開・添付ファイル）を追加"
```

---

## Task 2: send_job_service.py

**Files:**
- Create: `app/services/send_job_service.py`
- Create: `tests/test_send_job_service.py`

**Interfaces:**
- Consumes: `SendJob`, `SendLog`（models.py）
- Produces:
  - `create_job(session, name, template_id, staff_id) -> SendJob`
  - `start_job(session, job_id) -> None`  ← status を "sending" に
  - `finish_job(session, job_id) -> None`  ← status を "done" に、集計更新
  - `add_log(session, job_id, member_id, to_address, subject, status, error_message="") -> SendLog`
  - `get_jobs(session) -> list[SendJob]`
  - `get_job_logs(session, job_id) -> list[SendLog]`

- [ ] **Step 1: テストを書く**

```python
# tests/test_send_job_service.py
from app.database.models import EmailTemplate, Staff
from app.services.send_job_service import (
    create_job, start_job, finish_job, add_log,
    get_jobs, get_job_logs
)


def _setup(db_session):
    tmpl = EmailTemplate(name="案内", subject="件名", body="本文")
    staff = Staff(name="田中")
    db_session.add_all([tmpl, staff])
    db_session.flush()
    return tmpl, staff


def test_create_job(db_session):
    tmpl, staff = _setup(db_session)
    job = create_job(db_session, "2026年6月 総会案内", tmpl.id, staff.id)
    assert job.id is not None
    assert job.status == "draft"


def test_start_and_finish_job(db_session):
    tmpl, staff = _setup(db_session)
    job = create_job(db_session, "テストジョブ", tmpl.id, staff.id)
    start_job(db_session, job.id)
    db_session.refresh(job)
    assert job.status == "sending"
    finish_job(db_session, job.id)
    db_session.refresh(job)
    assert job.status == "done"
    assert job.sent_at is not None


def test_add_log_and_get(db_session):
    tmpl, staff = _setup(db_session)
    job = create_job(db_session, "テストジョブ", tmpl.id, staff.id)
    add_log(db_session, job.id, None, "a@example.com", "件名", "success")
    add_log(db_session, job.id, None, "b@example.com", "件名", "error",
            error_message="タイムアウト")
    logs = get_job_logs(db_session, job.id)
    assert len(logs) == 2
    errors = [l for l in logs if l.status == "error"]
    assert errors[0].error_message == "タイムアウト"


def test_finish_job_updates_counts(db_session):
    tmpl, staff = _setup(db_session)
    job = create_job(db_session, "テストジョブ", tmpl.id, staff.id)
    start_job(db_session, job.id)
    add_log(db_session, job.id, None, "a@example.com", "件名", "success")
    add_log(db_session, job.id, None, "b@example.com", "件名", "success")
    add_log(db_session, job.id, None, "c@example.com", "件名", "error")
    finish_job(db_session, job.id)
    db_session.refresh(job)
    assert job.total_count == 3
    assert job.success_count == 2
    assert job.error_count == 1
```

- [ ] **Step 2: テスト実行 → 失敗確認**

```bash
pytest tests/test_send_job_service.py -v
```

期待: `ImportError`

- [ ] **Step 3: send_job_service.py を作成**

```python
# app/services/send_job_service.py
from datetime import datetime
from sqlalchemy.orm import Session
from app.database.models import SendJob, SendLog


def create_job(session: Session, name: str,
               template_id: int, staff_id: int) -> SendJob:
    job = SendJob(name=name, template_id=template_id,
                  staff_id=staff_id, status="draft")
    session.add(job)
    session.commit()
    return job


def start_job(session: Session, job_id: int) -> None:
    job = session.get(SendJob, job_id)
    if job:
        job.status = "sending"
        session.commit()


def finish_job(session: Session, job_id: int) -> None:
    job = session.get(SendJob, job_id)
    if job is None:
        return
    logs = get_job_logs(session, job_id)
    job.total_count = len(logs)
    job.success_count = sum(1 for l in logs if l.status == "success")
    job.error_count = sum(1 for l in logs if l.status == "error")
    job.status = "done"
    job.sent_at = datetime.now()
    session.commit()


def add_log(session: Session, job_id: int, member_id: int | None,
            to_address: str, subject: str, status: str,
            error_message: str = "") -> SendLog:
    log = SendLog(
        job_id=job_id,
        member_id=member_id,
        to_address=to_address,
        subject=subject,
        status=status,
        error_message=error_message,
        sent_at=datetime.now() if status in ("success", "error") else None,
    )
    session.add(log)
    session.commit()
    return log


def get_jobs(session: Session) -> list[SendJob]:
    return (session.query(SendJob)
            .order_by(SendJob.created_at.desc())
            .all())


def get_job_logs(session: Session, job_id: int) -> list[SendLog]:
    return (session.query(SendLog)
            .filter_by(job_id=job_id)
            .order_by(SendLog.id)
            .all())
```

- [ ] **Step 4: テスト実行 → パス確認**

```bash
pytest tests/test_send_job_service.py -v
```

期待: `4 passed`

- [ ] **Step 5: コミット**

```bash
git add app/services/send_job_service.py tests/test_send_job_service.py
git commit -m "feat: 送信ジョブサービス（ジョブ管理・ログ記録）を追加"
```

---

## Task 3: 差し込みプレビューダイアログ + 添付確認ダイアログ

**Files:**
- Create: `app/ui/dialogs/merge_preview_dialog.py`
- Create: `app/ui/dialogs/attach_confirm_dialog.py`

**Interfaces:**
- `MergePreviewDialog(rows: list[dict], column_map: dict) -> QDialog`
  - `rows`: `[{"member_number": "A-001", "col1": "値1", ...}, ...]`
  - `get_merge_data() -> dict[str, dict]`  ← `{member_number: {col1, col2, ...}}`
- `AttachConfirmDialog(member_attach_list: list[dict]) -> QDialog`
  - `member_attach_list`: `[{"member_number": "A-001", "org_name": "○○商事", "to_address": "x@y.com", "filepath": "/path/A-001.pdf", "found": True}, ...]`
  - `get_approved_list() -> list[dict]`  ← found=Trueのもの（またはスキップ承認済み）

- [ ] **Step 1: merge_preview_dialog.py を作成**

```python
# app/ui/dialogs/merge_preview_dialog.py
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QPushButton, QLabel, QHBoxLayout, QFileDialog,
    QMessageBox
)
from app.services.import_service import load_member_file

_COL_KEYS = ["col1", "col2", "col3", "col4", "col5"]


class MergePreviewDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("差し込みデータ設定")
        self.resize(700, 500)
        self._merge_data: dict[str, dict] = {}
        self._col_names: list[str] = []
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            "差し込みデータCSV/ExcelをインポートしてCol1〜Col5に対応させます。\n"
            "「会員番号」列が必須です（名簿との突合キー）。"
        ))

        btn_row = QHBoxLayout()
        btn_import = QPushButton("ファイルを選択してインポート")
        btn_import.clicked.connect(self._import)
        btn_clear = QPushButton("クリア")
        btn_clear.clicked.connect(self._clear)
        btn_row.addWidget(btn_import)
        btn_row.addWidget(btn_clear)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self._table = QTableWidget(0, 7)
        self._table.setHorizontalHeaderLabels(
            ["会員番号", "col1", "col2", "col3", "col4", "col5", "マッピング列名"])
        self._table.horizontalHeader().setSectionResizeMode(
            6, QHeaderView.ResizeMode.Stretch)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self._table)

        self._status_label = QLabel("（未読み込み）")
        layout.addWidget(self._status_label)

        btn_close = QHBoxLayout()
        btn_ok = QPushButton("OK（このデータで送信）")
        btn_ok.clicked.connect(self.accept)
        btn_cancel = QPushButton("キャンセル（差し込みなし）")
        btn_cancel.clicked.connect(self.reject)
        btn_close.addWidget(btn_cancel)
        btn_close.addStretch()
        btn_close.addWidget(btn_ok)
        layout.addLayout(btn_close)

    def _import(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "差し込みデータを選択", "",
            "Excel/CSV (*.xlsx *.xls *.csv)")
        if not path:
            return
        try:
            headers, rows = load_member_file(path)
        except Exception as e:
            QMessageBox.critical(self, "エラー", str(e))
            return
        if not headers:
            QMessageBox.warning(self, "エラー", "ファイルが空です。")
            return

        # 列マッピングダイアログ
        from app.ui.dialogs._col_mapping_dialog import ColMappingDialog
        dlg = ColMappingDialog(headers, parent=self)
        if not dlg.exec():
            return
        mapping = dlg.get_mapping()  # {"member_number": idx, "col1": idx, ...}

        if "member_number" not in mapping:
            QMessageBox.warning(self, "エラー", "「会員番号」列のマッピングは必須です。")
            return

        self._merge_data = {}
        skipped = 0
        for row in rows:
            def cell(idx):
                if idx is None or idx >= len(row):
                    return ""
                v = row[idx]
                return str(v).strip() if v is not None else ""

            mn = cell(mapping.get("member_number"))
            if not mn:
                skipped += 1
                continue
            self._merge_data[mn] = {k: cell(mapping.get(k)) for k in _COL_KEYS}
            self._col_names = [headers[mapping[k]] if k in mapping else ""
                               for k in _COL_KEYS]

        self._refresh_table()
        self._status_label.setText(
            f"{len(self._merge_data)} 件読み込み済み。スキップ: {skipped} 件。")

    def _refresh_table(self):
        self._table.setRowCount(0)
        for mn, cols in self._merge_data.items():
            r = self._table.rowCount()
            self._table.insertRow(r)
            self._table.setItem(r, 0, QTableWidgetItem(mn))
            for i, k in enumerate(_COL_KEYS, 1):
                self._table.setItem(r, i, QTableWidgetItem(cols.get(k, "")))
            self._table.setItem(r, 6, QTableWidgetItem(
                " / ".join(n for n in self._col_names if n)))

    def _clear(self):
        self._merge_data = {}
        self._table.setRowCount(0)
        self._status_label.setText("（クリア済み）")

    def get_merge_data(self) -> dict[str, dict]:
        return self._merge_data
```

```python
# app/ui/dialogs/_col_mapping_dialog.py
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QComboBox, QPushButton,
    QHBoxLayout, QLabel
)

_FIELD_LABELS = [
    ("member_number", "会員番号 *"),
    ("col1", "col1"),
    ("col2", "col2"),
    ("col3", "col3"),
    ("col4", "col4"),
    ("col5", "col5"),
]


class ColMappingDialog(QDialog):
    def __init__(self, headers: list[str], parent=None):
        super().__init__(parent)
        self.setWindowTitle("列マッピング")
        self._headers = headers
        self._combos: dict[str, QComboBox] = {}
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("各フィールドに対応するファイルの列を選択してください。"))
        form = QFormLayout()
        for field_key, label in _FIELD_LABELS:
            combo = QComboBox()
            combo.addItem("（使用しない）", None)
            for i, h in enumerate(self._headers):
                combo.addItem(h, i)
            # 自動マッピング
            lower_h = [h.lower() for h in self._headers]
            auto_keys = {"member_number": ["会員番号", "membernumber", "member_number"]}
            for k in auto_keys.get(field_key, []):
                if k in lower_h:
                    combo.setCurrentIndex(lower_h.index(k) + 1)
                    break
            self._combos[field_key] = combo
            form.addRow(label, combo)
        layout.addLayout(form)
        btn_row = QHBoxLayout()
        btn_cancel = QPushButton("キャンセル")
        btn_cancel.clicked.connect(self.reject)
        btn_ok = QPushButton("OK")
        btn_ok.clicked.connect(self.accept)
        btn_row.addWidget(btn_cancel)
        btn_row.addStretch()
        btn_row.addWidget(btn_ok)
        layout.addLayout(btn_row)

    def get_mapping(self) -> dict[str, int]:
        result = {}
        for field_key, combo in self._combos.items():
            idx = combo.currentData()
            if idx is not None:
                result[field_key] = idx
        return result
```

```python
# app/ui/dialogs/attach_confirm_dialog.py
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QPushButton, QHBoxLayout, QLabel, QMessageBox
)
from PyQt6.QtGui import QColor


class AttachConfirmDialog(QDialog):
    def __init__(self, member_attach_list: list[dict], parent=None):
        super().__init__(parent)
        self.setWindowTitle("個別添付ファイル確認")
        self.resize(750, 500)
        self._list = member_attach_list
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        missing = sum(1 for r in self._list if not r["found"])
        if missing:
            layout.addWidget(QLabel(
                f"⚠ ファイルが見つからない企業が {missing} 件あります（×印）。\n"
                "「スキップして続行」を選ぶと、×印の企業は添付なしで送信されます。"
            ))

        self._table = QTableWidget(0, 5)
        self._table.setHorizontalHeaderLabels(
            ["事業所名", "会員番号", "送信先アドレス", "対応ファイル名", "確認"])
        self._table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self._table)

        for r in self._list:
            row = self._table.rowCount()
            self._table.insertRow(row)
            self._table.setItem(row, 0, QTableWidgetItem(r["org_name"]))
            self._table.setItem(row, 1, QTableWidgetItem(r["member_number"]))
            self._table.setItem(row, 2, QTableWidgetItem(r["to_address"]))
            import os
            fname = os.path.basename(r["filepath"]) if r["filepath"] else "—"
            self._table.setItem(row, 3, QTableWidgetItem(fname))
            found_item = QTableWidgetItem("○" if r["found"] else "×")
            if not r["found"]:
                found_item.setForeground(QColor("red"))
            self._table.setItem(row, 4, found_item)

        btn_row = QHBoxLayout()
        btn_cancel = QPushButton("中止")
        btn_cancel.clicked.connect(self.reject)
        btn_skip = QPushButton("スキップして続行（×印は添付なし）")
        btn_skip.clicked.connect(self.accept)
        btn_row.addWidget(btn_cancel)
        btn_row.addStretch()
        btn_row.addWidget(btn_skip)
        layout.addLayout(btn_row)

    def get_approved_list(self) -> list[dict]:
        return self._list
```

- [ ] **Step 2: コミット**

```bash
git add app/ui/dialogs/merge_preview_dialog.py \
        app/ui/dialogs/attach_confirm_dialog.py \
        app/ui/dialogs/_col_mapping_dialog.py
git commit -m "feat: 差し込みプレビューダイアログ・個別添付確認ダイアログを追加"
```

---

## Task 4: メール送信タブ（send_tab.py）

**Files:**
- Modify: `app/ui/send_tab.py`（プレースホルダーを置き換え）

**Interfaces:**
- Consumes: 全サービス（member_service, template_service, signature_service, email_service, send_job_service）、全ダイアログ

- [ ] **Step 1: send_tab.py を実装**

```python
# app/ui/send_tab.py
import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QScrollArea,
    QGroupBox, QFormLayout, QComboBox, QLabel,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QPushButton, QCheckBox, QLineEdit, QTextEdit,
    QProgressBar, QFileDialog, QMessageBox, QSizePolicy
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from app.database.connection import get_session
from app.services.member_service import get_members, get_member
from app.services.template_service import get_templates, get_template
from app.services.signature_service import get_signatures, get_default_signature
from app.services.position_service import get_positions
from app.services.staff_service import get_active_staff
from app.services.email_service import render_body, send_mail, send_test_mail
from app.services.send_job_service import (
    create_job, start_job, finish_job, add_log
)
from app.utils.app_config import get_graph_config


class _SendWorker(QThread):
    progress = pyqtSignal(int, int, str)   # current, total, message
    finished = pyqtSignal(int, int, int)   # success, error, skip

    def __init__(self, targets: list[dict], graph_config: dict,
                 job_id: int, session):
        super().__init__()
        self._targets = targets
        self._graph_config = graph_config
        self._job_id = job_id
        self._session = session

    def run(self):
        success = error = skip = 0
        total = len(self._targets)
        for i, t in enumerate(self._targets, 1):
            to_addr = t["to_address"]
            if not to_addr:
                add_log(self._session, self._job_id, t.get("member_id"),
                        "", t["subject"], "skip")
                skip += 1
                self.progress.emit(i, total, f"スキップ: {t['org_name']}")
                continue
            try:
                send_mail(
                    self._graph_config,
                    to_addr,
                    t["subject"],
                    t["body"],
                    t.get("attachments", []),
                )
                add_log(self._session, self._job_id, t.get("member_id"),
                        to_addr, t["subject"], "success")
                success += 1
                self.progress.emit(i, total, f"送信済: {t['org_name']}")
            except Exception as e:
                add_log(self._session, self._job_id, t.get("member_id"),
                        to_addr, t["subject"], "error", str(e))
                error += 1
                self.progress.emit(i, total, f"エラー: {t['org_name']} — {e}")
        self.finished.emit(success, error, skip)


class SendTab(QWidget):
    def __init__(self):
        super().__init__()
        self._selected_member_ids: list[int] = []
        self._merge_data: dict[str, dict] = {}
        self._common_attachments: list[str] = []
        self._individual_folder: str = ""
        self._individual_rule: str = ""
        self._attach_list: list[dict] = []
        self._build()

    def _build(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        layout = QVBoxLayout(inner)

        # Step 1: 操作者
        grp1 = QGroupBox("Step 1：操作者選択")
        f1 = QFormLayout(grp1)
        self._staff_combo = QComboBox()
        f1.addRow("操作者", self._staff_combo)
        layout.addWidget(grp1)

        # Step 2: 宛先選択
        grp2 = QGroupBox("Step 2：宛先選択")
        v2 = QVBoxLayout(grp2)
        v2.addWidget(QLabel("役職で選択："))
        self._pos_checks: dict[int, QCheckBox] = {}
        self._pos_check_layout = QHBoxLayout()
        v2.addLayout(self._pos_check_layout)
        v2.addWidget(QLabel("企業で選択："))
        self._member_table = QTableWidget(0, 3)
        self._member_table.setHorizontalHeaderLabels(["選択", "事業所名", "氏名"])
        self._member_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch)
        self._member_table.setMaximumHeight(200)
        v2.addWidget(self._member_table)
        self._selection_label = QLabel("選択中: 0 件")
        v2.addWidget(self._selection_label)
        layout.addWidget(grp2)

        # Step 3: テンプレート・署名
        grp3 = QGroupBox("Step 3：テンプレート・署名選択")
        f3 = QFormLayout(grp3)
        self._template_combo = QComboBox()
        self._template_combo.currentIndexChanged.connect(self._on_template_select)
        self._sig_combo = QComboBox()
        self._subject_edit = QLineEdit()
        self._body_edit = QTextEdit()
        self._body_edit.setMaximumHeight(150)
        f3.addRow("テンプレート", self._template_combo)
        f3.addRow("署名", self._sig_combo)
        f3.addRow("件名", self._subject_edit)
        f3.addRow("本文", self._body_edit)
        layout.addWidget(grp3)

        # Step 4: 差し込みデータ
        grp4 = QGroupBox("Step 4：差し込みデータ（任意）")
        v4 = QVBoxLayout(grp4)
        btn_merge = QPushButton("CSV/Excelをインポート")
        btn_merge.clicked.connect(self._import_merge)
        self._merge_status = QLabel("（未読み込み — col1〜col5は空で送信）")
        v4.addWidget(btn_merge)
        v4.addWidget(self._merge_status)
        layout.addWidget(grp4)

        # Step 5: 添付ファイル
        grp5 = QGroupBox("Step 5：添付ファイル（任意）")
        v5 = QVBoxLayout(grp5)

        common_row = QHBoxLayout()
        btn_common = QPushButton("全社共通ファイルを選択")
        btn_common.clicked.connect(self._select_common_attach)
        self._common_label = QLabel("（未選択）")
        common_row.addWidget(btn_common)
        common_row.addWidget(self._common_label)
        v5.addLayout(common_row)

        indiv_row = QHBoxLayout()
        btn_folder = QPushButton("会社別フォルダを選択")
        btn_folder.clicked.connect(self._select_indiv_folder)
        self._folder_label = QLabel("（未選択）")
        indiv_row.addWidget(btn_folder)
        indiv_row.addWidget(self._folder_label)
        v5.addLayout(indiv_row)

        rule_row = QHBoxLayout()
        rule_row.addWidget(QLabel("ファイル名ルール:"))
        self._rule_edit = QLineEdit("{会員番号}.pdf")
        rule_row.addWidget(self._rule_edit)
        btn_match = QPushButton("マッチング確認")
        btn_match.clicked.connect(self._check_matching)
        rule_row.addWidget(btn_match)
        v5.addLayout(rule_row)
        self._match_label = QLabel("")
        v5.addWidget(self._match_label)
        layout.addWidget(grp5)

        # Step 6: 送信
        grp6 = QGroupBox("Step 6：最終確認・送信")
        v6 = QVBoxLayout(grp6)
        self._job_name = QLineEdit()
        self._job_name.setPlaceholderText("例：2026年6月 総会案内")
        f6 = QFormLayout()
        f6.addRow("ジョブ名", self._job_name)
        v6.addLayout(f6)
        self._preview_table = QTableWidget(0, 4)
        self._preview_table.setHorizontalHeaderLabels(
            ["事業所名", "送信先アドレス", "添付", "col1"])
        self._preview_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch)
        self._preview_table.setMaximumHeight(200)
        v6.addWidget(self._preview_table)
        btn_row6 = QHBoxLayout()
        btn_preview = QPushButton("プレビュー更新")
        btn_preview.clicked.connect(self._refresh_preview)
        btn_test = QPushButton("テスト送信（1通）")
        btn_test.clicked.connect(self._test_send)
        btn_send = QPushButton("送信実行")
        btn_send.setStyleSheet("font-weight: bold; background-color: #1E40AF; color: white;")
        btn_send.clicked.connect(self._execute_send)
        btn_row6.addWidget(btn_preview)
        btn_row6.addWidget(btn_test)
        btn_row6.addStretch()
        btn_row6.addWidget(btn_send)
        v6.addLayout(btn_row6)
        self._progress = QProgressBar()
        self._progress.setVisible(False)
        self._progress_label = QLabel("")
        v6.addWidget(self._progress)
        v6.addWidget(self._progress_label)
        layout.addWidget(grp6)

        scroll.setWidget(inner)
        main_layout = QVBoxLayout(self)
        main_layout.addWidget(scroll)
        self._load_combos()

    def _load_combos(self):
        session = get_session()
        try:
            # 職員
            staff_list = get_active_staff(session)
            self._staff_combo.clear()
            self._staff_combo.addItem("（選択してください）", None)
            for s in staff_list:
                self._staff_combo.addItem(s.name, s.id)

            # 役職チェックボックス
            for cb in self._pos_checks.values():
                cb.deleteLater()
            self._pos_checks.clear()
            positions = get_positions(session)
            for p in positions:
                cb = QCheckBox(p.name)
                cb.stateChanged.connect(self._on_pos_check)
                self._pos_check_layout.addWidget(cb)
                self._pos_checks[p.id] = cb

            # 会員テーブル
            members = get_members(session)
            self._members = members
            self._member_table.setRowCount(0)
            for m in members:
                row = self._member_table.rowCount()
                self._member_table.insertRow(row)
                cb = QCheckBox()
                cb.stateChanged.connect(self._on_member_check)
                self._member_table.setCellWidget(row, 0, cb)
                self._member_table.setItem(row, 1, QTableWidgetItem(m.organization_name))
                self._member_table.setItem(row, 2, QTableWidgetItem(m.name))
                self._member_table.item(row, 1).setData(Qt.ItemDataRole.UserRole, m.id)

            # テンプレート
            templates = get_templates(session)
            self._templates = templates
            self._template_combo.clear()
            self._template_combo.addItem("（選択してください）", None)
            for t in templates:
                self._template_combo.addItem(t.name, t.id)

            # 署名
            signatures = get_signatures(session)
            self._signatures = signatures
            self._sig_combo.clear()
            self._sig_combo.addItem("（なし）", None)
            for s in signatures:
                self._sig_combo.addItem(s.name, s.id)
            default_sig = get_default_signature(session)
            if default_sig:
                for i in range(self._sig_combo.count()):
                    if self._sig_combo.itemData(i) == default_sig.id:
                        self._sig_combo.setCurrentIndex(i)
                        break
        finally:
            session.close()

    def _on_pos_check(self):
        session = get_session()
        try:
            checked_pos_ids = {pid for pid, cb in self._pos_checks.items()
                               if cb.isChecked()}
            for row in range(self._member_table.rowCount()):
                item = self._member_table.item(row, 1)
                mid = item.data(Qt.ItemDataRole.UserRole) if item else None
                if mid is None:
                    continue
                m = next((x for x in self._members if x.id == mid), None)
                if m and m.position_id in checked_pos_ids:
                    cb = self._member_table.cellWidget(row, 0)
                    if cb:
                        cb.blockSignals(True)
                        cb.setChecked(True)
                        cb.blockSignals(False)
        finally:
            session.close()
        self._update_selection_label()

    def _on_member_check(self):
        self._update_selection_label()

    def _update_selection_label(self):
        count = sum(
            1 for row in range(self._member_table.rowCount())
            if (cb := self._member_table.cellWidget(row, 0)) and cb.isChecked()
        )
        self._selection_label.setText(f"選択中: {count} 件")

    def _get_selected_members(self) -> list:
        session = get_session()
        try:
            result = []
            seen = set()
            for row in range(self._member_table.rowCount()):
                cb = self._member_table.cellWidget(row, 0)
                if not (cb and cb.isChecked()):
                    continue
                item = self._member_table.item(row, 1)
                mid = item.data(Qt.ItemDataRole.UserRole) if item else None
                if mid and mid not in seen:
                    seen.add(mid)
                    m = get_member(session, mid)
                    if m:
                        result.append(m)
            return result
        finally:
            session.close()

    def _on_template_select(self):
        tmpl_id = self._template_combo.currentData()
        if not tmpl_id:
            return
        session = get_session()
        try:
            t = get_template(session, tmpl_id)
            if t:
                self._subject_edit.setText(t.subject)
                self._body_edit.setPlainText(t.body)
                if t.signature_id:
                    for i in range(self._sig_combo.count()):
                        if self._sig_combo.itemData(i) == t.signature_id:
                            self._sig_combo.setCurrentIndex(i)
                            break
        finally:
            session.close()

    def _import_merge(self):
        from app.ui.dialogs.merge_preview_dialog import MergePreviewDialog
        dlg = MergePreviewDialog(parent=self)
        if dlg.exec():
            self._merge_data = dlg.get_merge_data()
            self._merge_status.setText(
                f"{len(self._merge_data)} 件の差し込みデータを読み込み済み")
        else:
            self._merge_data = {}
            self._merge_status.setText("（差し込みなし — col1〜col5は空で送信）")

    def _select_common_attach(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "添付ファイルを選択", "")
        if paths:
            self._common_attachments = paths
            names = ", ".join(os.path.basename(p) for p in paths)
            self._common_label.setText(names)

    def _select_indiv_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "フォルダを選択")
        if folder:
            self._individual_folder = folder
            self._folder_label.setText(folder)

    def _check_matching(self):
        if not self._individual_folder:
            QMessageBox.warning(self, "エラー", "フォルダを先に選択してください。")
            return
        rule = self._rule_edit.text().strip()
        members = self._get_selected_members()
        if not members:
            QMessageBox.warning(self, "エラー", "宛先を先に選択してください。")
            return
        self._attach_list = []
        for m in members:
            to_addr = m.email_addresses[0].address if m.email_addresses else ""
            fname = rule.replace("{会員番号}", m.member_number)
            fpath = os.path.join(self._individual_folder, fname)
            self._attach_list.append({
                "member_number": m.member_number,
                "org_name":      m.organization_name,
                "to_address":    to_addr,
                "filepath":      fpath,
                "found":         os.path.exists(fpath),
            })
        found = sum(1 for r in self._attach_list if r["found"])
        missing = len(self._attach_list) - found
        self._match_label.setText(
            f"マッチング: {found}/{len(self._attach_list)} 件。未発見: {missing} 件")
        if missing > 0:
            from app.ui.dialogs.attach_confirm_dialog import AttachConfirmDialog
            dlg = AttachConfirmDialog(self._attach_list, parent=self)
            dlg.exec()

    def _build_targets(self) -> list[dict]:
        members = self._get_selected_members()
        subject_tpl = self._subject_edit.text()
        body_tpl = self._body_edit.toPlainText()

        # 署名
        sig_id = self._sig_combo.currentData()
        sig_body = ""
        if sig_id:
            sig = next((s for s in self._signatures if s.id == sig_id), None)
            if sig:
                sig_body = "\n\n" + sig.body

        attach_map: dict[str, list[str]] = {}
        if self._attach_list:
            for r in self._attach_list:
                if r["found"]:
                    attach_map[r["member_number"]] = [r["filepath"]]

        targets = []
        for m in members:
            to_addr = m.email_addresses[0].address if m.email_addresses else ""
            merge = self._merge_data.get(m.member_number, {})
            context = {
                "事業所名":     m.organization_name,
                "役職名":       m.title or "",
                "氏名":         m.name,
                "会議所役職名": m.position.name if m.position else "",
                **{k: merge.get(k, "") for k in ["col1","col2","col3","col4","col5"]},
            }
            subject = render_body(subject_tpl, context)
            body = render_body(body_tpl + sig_body, context)
            attachments = list(self._common_attachments)
            attachments.extend(attach_map.get(m.member_number, []))
            targets.append({
                "member_id":  m.id,
                "org_name":   m.organization_name,
                "to_address": to_addr,
                "subject":    subject,
                "body":       body,
                "attachments": attachments,
            })
        return targets

    def _refresh_preview(self):
        targets = self._build_targets()
        self._preview_table.setRowCount(0)
        for t in targets:
            row = self._preview_table.rowCount()
            self._preview_table.insertRow(row)
            self._preview_table.setItem(row, 0, QTableWidgetItem(t["org_name"]))
            self._preview_table.setItem(row, 1, QTableWidgetItem(t["to_address"]))
            has_attach = "あり" if t["attachments"] else ""
            self._preview_table.setItem(row, 2, QTableWidgetItem(has_attach))
            col1 = t["body"][:30] if t["body"] else ""
            self._preview_table.setItem(row, 3, QTableWidgetItem(col1))

    def _test_send(self):
        targets = self._build_targets()
        if not targets:
            QMessageBox.warning(self, "エラー", "宛先を選択してください。")
            return
        graph_config = get_graph_config()
        if not graph_config.get("test_address"):
            QMessageBox.warning(self, "エラー",
                                "設定タブでテスト送信先アドレスを設定してください。")
            return
        t = targets[0]
        try:
            send_test_mail(graph_config, t["subject"], t["body"])
            QMessageBox.information(self, "完了",
                                    f"テストメールを送信しました。\n宛先: {graph_config['test_address']}")
        except Exception as e:
            QMessageBox.critical(self, "エラー", str(e))

    def _execute_send(self):
        targets = self._build_targets()
        if not targets:
            QMessageBox.warning(self, "エラー", "宛先を選択してください。")
            return
        job_name = self._job_name.text().strip()
        if not job_name:
            QMessageBox.warning(self, "エラー", "ジョブ名を入力してください。")
            return
        staff_id = self._staff_combo.currentData()
        if not staff_id:
            QMessageBox.warning(self, "エラー", "操作者を選択してください。")
            return
        graph_config = get_graph_config()
        if not graph_config.get("tenant_id"):
            QMessageBox.warning(self, "エラー",
                                "設定タブでMicrosoft 365設定を行ってください。")
            return

        ret = QMessageBox.question(
            self, "送信確認",
            f"{len(targets)} 件に送信します。よろしいですか？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if ret != QMessageBox.StandardButton.Yes:
            return

        session = get_session()
        tmpl_id = self._template_combo.currentData()
        job = create_job(session, job_name, tmpl_id, staff_id)
        start_job(session, job.id)

        self._progress.setVisible(True)
        self._progress.setMaximum(len(targets))
        self._progress.setValue(0)

        self._worker = _SendWorker(targets, graph_config, job.id, session)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(
            lambda s, e, sk: self._on_finished(job.id, s, e, sk, session))
        self._worker.start()

    def _on_progress(self, current: int, total: int, message: str):
        self._progress.setValue(current)
        self._progress_label.setText(f"[{current}/{total}] {message}")

    def _on_finished(self, job_id: int, success: int, error: int, skip: int, session):
        finish_job(session, job_id)
        session.close()
        self._progress.setVisible(False)
        QMessageBox.information(
            self, "送信完了",
            f"送信完了\n\n成功: {success} 件\nエラー: {error} 件\nスキップ: {skip} 件\n\n"
            "「送信履歴」タブで詳細を確認できます。"
        )
```

- [ ] **Step 2: 全テスト確認**

```bash
pytest tests/ -v
```

期待: 全テストがパス

- [ ] **Step 3: コミット**

```bash
git add app/ui/send_tab.py
git commit -m "feat: メール送信タブ（6ステップ送信フロー・Graph API）を実装 — Plan 4完了"
```

---

## Plan 4 完了チェックリスト

- [ ] `pytest tests/ -v` で全テストがパス
- [ ] テンプレートの `{事業所名}` `{氏名}` `{col1}` がメール本文に正しく展開される
- [ ] 差し込みCSVをインポートして col1〜col5 が展開される
- [ ] 個別添付ファイルのマッチング確認テーブルが表示される
- [ ] テスト送信ボタンで1通送信できる（Graph API設定済みの場合）
- [ ] 送信実行でプログレスバーが表示され、完了サマリーが出る
