# cci-mail Plan 5: 送信履歴タブ

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 送信履歴タブ（ジョブ一覧・明細表示・CSV出力）を実装してシステムを完成させる。

**Architecture:** `send_job_service.py` の `get_jobs()` / `get_job_logs()` を使ってUI層のみ実装。サービス層は Plan 4 で完成している。

**Tech Stack:** Python 3.11+, PyQt6, csv, pytest

## Global Constraints

- Plan 1〜4が完了していること
- テストはインメモリSQLite（conftest.pyのdb_sessionフィクスチャ）を使用

---

## ファイル構成（変更のみ）

```
app/
  ui/
    history_tab.py   # Plan 1プレースホルダーを置き換え
```

---

## Task 1: 送信履歴タブ

**Files:**
- Modify: `app/ui/history_tab.py`（プレースホルダーを置き換え）

**Interfaces:**
- Consumes: `get_jobs()`, `get_job_logs()`（send_job_service.py）

- [ ] **Step 1: history_tab.py を実装**

```python
# app/ui/history_tab.py
import csv
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QPushButton, QLabel, QFileDialog, QMessageBox
)
from PyQt6.QtCore import Qt
from app.database.connection import get_session
from app.services.send_job_service import get_jobs, get_job_logs


class HistoryTab(QWidget):
    def __init__(self):
        super().__init__()
        self._jobs = []
        self._logs = []
        self._build()
        self._load_jobs()

    def _build(self):
        layout = QVBoxLayout(self)

        # ツールバー
        toolbar = QHBoxLayout()
        btn_refresh = QPushButton("更新")
        btn_refresh.clicked.connect(self._load_jobs)
        btn_export = QPushButton("CSV出力")
        btn_export.clicked.connect(self._export_csv)
        toolbar.addWidget(btn_refresh)
        toolbar.addStretch()
        toolbar.addWidget(btn_export)
        layout.addLayout(toolbar)

        splitter = QSplitter(Qt.Orientation.Vertical)

        # 上段: ジョブ一覧
        job_widget = QWidget()
        job_layout = QVBoxLayout(job_widget)
        job_layout.addWidget(QLabel("送信ジョブ一覧"))
        self._job_table = QTableWidget(0, 6)
        self._job_table.setHorizontalHeaderLabels(
            ["送信日時", "操作者", "ジョブ名", "件数", "成功", "エラー"])
        self._job_table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.Stretch)
        self._job_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._job_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._job_table.currentRowChanged.connect(self._on_job_select)
        job_layout.addWidget(self._job_table)
        splitter.addWidget(job_widget)

        # 下段: 明細
        log_widget = QWidget()
        log_layout = QVBoxLayout(log_widget)
        log_layout.addWidget(QLabel("送信明細"))
        self._log_table = QTableWidget(0, 5)
        self._log_table.setHorizontalHeaderLabels(
            ["事業所名", "送信先アドレス", "件名", "結果", "エラー内容"])
        self._log_table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.Stretch)
        self._log_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        log_layout.addWidget(self._log_table)
        splitter.addWidget(log_widget)

        layout.addWidget(splitter)

    def _load_jobs(self):
        session = get_session()
        try:
            self._jobs = get_jobs(session)
        finally:
            session.close()

        self._job_table.setRowCount(0)
        for j in self._jobs:
            row = self._job_table.rowCount()
            self._job_table.insertRow(row)
            sent_at = j.sent_at.strftime("%Y/%m/%d %H:%M") if j.sent_at else j.created_at.strftime("%Y/%m/%d %H:%M")
            staff_name = j.staff.name if j.staff else ""
            self._job_table.setItem(row, 0, QTableWidgetItem(sent_at))
            self._job_table.setItem(row, 1, QTableWidgetItem(staff_name))
            self._job_table.setItem(row, 2, QTableWidgetItem(j.name))
            self._job_table.setItem(row, 3, QTableWidgetItem(str(j.total_count)))
            self._job_table.setItem(row, 4, QTableWidgetItem(str(j.success_count)))
            self._job_table.setItem(row, 5, QTableWidgetItem(str(j.error_count)))
            self._job_table.item(row, 0).setData(Qt.ItemDataRole.UserRole, j.id)

        self._log_table.setRowCount(0)

    def _on_job_select(self, row: int):
        if row < 0 or row >= len(self._jobs):
            return
        job_id = self._job_table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        session = get_session()
        try:
            self._logs = get_job_logs(session, job_id)
        finally:
            session.close()

        self._log_table.setRowCount(0)
        for log in self._logs:
            r = self._log_table.rowCount()
            self._log_table.insertRow(r)
            org_name = log.member.organization_name if log.member else ""
            self._log_table.setItem(r, 0, QTableWidgetItem(org_name))
            self._log_table.setItem(r, 1, QTableWidgetItem(log.to_address))
            self._log_table.setItem(r, 2, QTableWidgetItem(log.subject))
            status_label = {"success": "成功", "error": "エラー", "skip": "スキップ"}.get(
                log.status, log.status)
            self._log_table.setItem(r, 3, QTableWidgetItem(status_label))
            self._log_table.setItem(r, 4, QTableWidgetItem(log.error_message or ""))

    def _export_csv(self):
        row = self._job_table.currentRow()
        if row < 0:
            QMessageBox.information(self, "情報", "エクスポートするジョブを選択してください。")
            return
        if not self._logs:
            QMessageBox.information(self, "情報", "明細データがありません。")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "CSV保存", "", "CSV (*.csv)")
        if not path:
            return
        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                writer.writerow(["事業所名", "送信先アドレス", "件名", "結果",
                                  "エラー内容", "送信日時"])
                for log in self._logs:
                    org_name = log.member.organization_name if log.member else ""
                    sent_at = log.sent_at.strftime("%Y/%m/%d %H:%M") if log.sent_at else ""
                    status_label = {"success": "成功", "error": "エラー",
                                    "skip": "スキップ"}.get(log.status, log.status)
                    writer.writerow([org_name, log.to_address, log.subject,
                                     status_label, log.error_message or "", sent_at])
            QMessageBox.information(self, "完了", f"CSVを保存しました。\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "エラー", str(e))
```

- [ ] **Step 2: 全テスト確認**

```bash
pytest tests/ -v
```

期待: 全テストがパス

- [ ] **Step 3: 起動確認**

```bash
python main.py
```

確認項目:
- 全5タブが表示される
- 名簿管理タブ: 追加・編集・削除・変更履歴・インポートが動作する
- テンプレートタブ: テンプレートのCRUDが動作する
- 設定タブ: 職員・役職・署名・Graph API設定が動作する
- 送信履歴タブ: ジョブ一覧・明細・CSV出力が動作する

- [ ] **Step 4: コミット**

```bash
git add app/ui/history_tab.py
git commit -m "feat: 送信履歴タブ（ジョブ一覧・明細・CSV出力）を実装 — Plan 5完了・システム完成"
```

---

## Plan 5 完了チェックリスト（＝システム全体完了チェック）

- [ ] `pytest tests/ -v` で全テストがパス
- [ ] `python main.py` でウィンドウが起動する（780×728px以内）
- [ ] 設定タブ → Microsoft 365 設定を保存・接続テストできる
- [ ] 設定タブ → 会議所役職を追加・編集できる
- [ ] 設定タブ → 職員を追加・有効/無効切り替えできる
- [ ] 設定タブ → 署名を追加・デフォルト設定できる
- [ ] 名簿管理タブ → 会員を追加・編集でき、変更理由が必須になっている
- [ ] 名簿管理タブ → 変更履歴を閲覧できる
- [ ] 名簿管理タブ → ExcelをインポートしてCSVをインポートできる
- [ ] テンプレートタブ → テンプレートを作成・編集できる
- [ ] メール送信タブ → 役職・企業のチェックボックスで宛先を選択できる
- [ ] メール送信タブ → 差し込みCSVをインポートして col1〜col5 が設定される
- [ ] メール送信タブ → 個別添付マッチング確認テーブルが表示される
- [ ] メール送信タブ → テスト送信が実行できる（Graph API設定済みの場合）
- [ ] 送信履歴タブ → 送信ジョブの一覧と明細を確認できる
- [ ] 送信履歴タブ → CSV出力ができる
- [ ] `cci_mail.db` が共有フォルダに置かれた状態でも `python main.py` が起動する
