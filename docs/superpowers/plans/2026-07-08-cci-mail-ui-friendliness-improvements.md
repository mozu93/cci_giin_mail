# cci-mail UI友好性改善 実装計画

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 「商工会議所メール配信システム UIユーザーフレンドリー評価」で指摘された16件の改善提案（優先度：高4・中6・低6）を、既存の設計・実装パターンを踏襲しながら小さな単位で実装する。

**Architecture:** 既存の各タブ／ダイアログ（`app/ui/*.py`, `app/ui/dialogs/*.py`）に対する局所的な修正の積み重ね。新しい共通部品は「保存完了インライン表示」ヘルパー（`app/ui/widgets/inline_status.py`）のみ新規作成し、それ以外はサービス層（`app/services/*`）・DBスキーマに変更を加えない。

**Tech Stack:** Python 3.11+, PyQt6, SQLAlchemy, pytest, pytest-qt

## Global Constraints

- ウィンドウ初期サイズは 780×728px 以内に収めること（`C:\Users\taka\.claude\CLAUDE.md` の全プロジェクト共通ルール）。評価書の「低優先度」提案のうち初期ウィンドウサイズを拡大する案は、このルールと矛盾するため **本計画の対象外とする**（Task一覧末尾の「対象外事項」参照）。
- 既存の命名規則・ディレクトリ構成・実装パターン（`get_session()` の都度生成、`QMessageBox` の使い方、`settings_service.py` の JSON永続化パターンなど）を踏襲する。
- サービス層・DBスキーマ・既存の公開関数シグネチャは変更しない（UI層のみの変更に限定）。
- 各タスクは独立して実装・テスト・コミット可能。依存関係がある場合のみ Task 番号順を守る（依存関係は各Taskの Interfaces に明記）。
- テストは `tests/conftest.py` の `db_session` フィクスチャ、または pytest-qt の `qtbot` フィクスチャを使う。実DB（`get_session()`）へのアクセスが発生する箇所は `monkeypatch` でサービス関数を差し替え、テストがローカルの `app_config.json` / 実DBに依存しないようにする。

---

## タスク一覧（優先度順）

| # | 優先度 | 内容 | 対象ファイル |
|---|---|---|---|
| 1 | 高 | 送信中止ボタン | send_tab.py |
| 2 | 高 | 破壊的操作ダイアログの既定ボタンをNoに | meeting_tab.py, member_tab.py, settings_tab.py, template_tab.py, import_revert_dialog.py, send_tab.py |
| 3 | 高 | テンプレート編集の未保存変更警告 | template_tab.py |
| 4 | 高 | 会員編集ダイアログの未保存変更警告 | member_edit_dialog.py |
| 5 | 高 | 署名本文をQTextEditに変更 | settings_tab.py |
| 6 | 高 | 送信履歴タブ・名簿タブの自動更新 | history_tab.py, member_tab.py |
| 7 | 中 | 宛先一覧の「表示中を全選択/全解除」 | recipient_panel.py |
| 8 | 中 | 保存完了メッセージをインライン表示に | settings_tab.py, template_tab.py, app/ui/widgets/inline_status.py（新規） |
| 9 | 中 | インポートダイアログにデータプレビュー | import_dialog.py |
| 10 | 中 | 名簿タブに編集系ボタンをツールバーに追加 | member_tab.py |
| 11 | 中 | 送信タブ本文欄の高さ緩和 | send_tab.py |
| 12 | 中 | 一括削除機能を開発者向けフラグで隠す | settings_tab.py |
| 13 | 低 | 名簿テーブルのメール列集約 | member_tab.py |
| 14 | 低 | 名簿・送信履歴テーブルのソート機能 | member_tab.py, history_tab.py |
| 15 | 低 | 空状態のガイダンス表示 | member_tab.py, template_tab.py |
| 16 | 低 | キーボードショートカット（Ctrl+S / Ctrl+F） | template_tab.py, member_tab.py |
| 17 | 低 | ログインダイアログ改善（未選択時ボタン無効化＋前回担当者記憶） | login_dialog.py, settings_service.py |

---

## Task 1: 送信中止ボタン

**Files:**
- Modify: `app/ui/send_tab.py:23-60`（`_SendWorker`）, `app/ui/send_tab.py:254-284`（`_build_step5`）, `app/ui/send_tab.py:599-671`（`_execute_send` 〜 `_on_finished`）
- Test: `tests/test_send_worker_cancel.py`（新規）

**Interfaces:**
- Produces: `_SendWorker.request_cancel()`（中止フラグを立てる）、`_SendWorker.cancelled` シグナルなし（`finished` シグナルの `skip` に未送信分を合算して通知）

- [ ] **Step 1: 失敗するテストを書く**

```python
# tests/test_send_worker_cancel.py
import pytest
from app.ui.send_tab import _SendWorker


def test_cancel_stops_before_remaining_targets(monkeypatch):
    sent = []

    def fake_send_mail(graph_config, to_addr, subject, body, attachments):
        sent.append(to_addr)
        if len(sent) == 1:
            worker.request_cancel()

    def fake_add_log(session, job_id, member_id, to_addr, subject, status, error=None):
        pass

    monkeypatch.setattr("app.ui.send_tab.send_mail", fake_send_mail)
    monkeypatch.setattr("app.ui.send_tab.add_log", fake_add_log)
    monkeypatch.setattr("app.ui.send_tab.get_session", lambda: _FakeSession())

    targets = [
        {"to_address": f"a{i}@example.com", "subject": "s", "body": "b",
         "org_name": f"org{i}", "member_id": i, "attachments": []}
        for i in range(5)
    ]
    worker = _SendWorker(targets, {}, job_id=1)
    worker.run()

    assert sent == ["a0@example.com"]


class _FakeSession:
    def close(self):
        pass
```

- [ ] **Step 2: テストを実行して失敗を確認**

Run: `pytest tests/test_send_worker_cancel.py -v`
Expected: FAIL — `AttributeError: '_SendWorker' object has no attribute 'request_cancel'`

- [ ] **Step 3: `_SendWorker` に中止フラグを実装**

`app/ui/send_tab.py:23-60` を以下に置き換える:

```python
class _SendWorker(QThread):
    progress = pyqtSignal(int, int, str)
    finished = pyqtSignal(int, int, int)

    def __init__(self, targets: list[dict], graph_config: dict, job_id: int):
        super().__init__()
        self._targets = targets
        self._graph_config = graph_config
        self._job_id = job_id
        self._cancelled = False

    def request_cancel(self):
        self._cancelled = True

    def run(self):
        session = get_session()
        try:
            success = error = skip = 0
            total = len(self._targets)
            for i, t in enumerate(self._targets, 1):
                if self._cancelled:
                    remaining = total - i + 1
                    skip += remaining
                    self.progress.emit(
                        total, total, f"中止しました（残り{remaining}件は未送信）")
                    break
                to_addr = t["to_address"]
                if not to_addr:
                    add_log(session, self._job_id, t.get("member_id"),
                            "", t["subject"], "skip")
                    skip += 1
                    self.progress.emit(i, total, f"スキップ: {t['org_name']}")
                    continue
                try:
                    send_mail(self._graph_config, to_addr, t["subject"],
                              t["body"], t.get("attachments", []))
                    add_log(session, self._job_id, t.get("member_id"),
                            to_addr, t["subject"], "success")
                    success += 1
                    self.progress.emit(i, total, f"送信済: {t['org_name']}")
                except Exception as e:
                    add_log(session, self._job_id, t.get("member_id"),
                            to_addr, t["subject"], "error", str(e))
                    error += 1
                    self.progress.emit(i, total, f"エラー: {t['org_name']} — {e}")
            self.finished.emit(success, error, skip)
        finally:
            session.close()
```

次に `app/ui/send_tab.py:264-277`（`_build_step5` のボタン行）を以下に置き換える:

```python
        btn_row = QHBoxLayout()
        btn_test = QPushButton("テスト送信（1通）")
        btn_test.clicked.connect(self._test_send)
        btn_preview = QPushButton("差し込みプレビュー")
        btn_preview.clicked.connect(self._show_send_preview)
        self._btn_send = QPushButton("送信実行")
        self._btn_send.setStyleSheet(
            "font-weight: bold; background-color: #1E40AF; color: white;")
        self._btn_send.clicked.connect(self._execute_send)
        self._btn_cancel = QPushButton("送信を中止")
        self._btn_cancel.setStyleSheet(
            "background-color: #DC2626; color: white;")
        self._btn_cancel.setVisible(False)
        self._btn_cancel.clicked.connect(self._cancel_send)
        btn_row.addWidget(btn_test)
        btn_row.addWidget(btn_preview)
        btn_row.addStretch()
        btn_row.addWidget(self._btn_cancel)
        btn_row.addWidget(self._btn_send)
        layout.addLayout(btn_row)
```

最後に `app/ui/send_tab.py:643-671`（`_execute_send` 後半 〜 `_on_finished`）を以下に置き換える:

```python
        self._progress.setVisible(True)
        self._progress.setMaximum(len(targets))
        self._progress.setValue(0)
        self._btn_send.setEnabled(False)
        self._btn_cancel.setVisible(True)

        self._worker = _SendWorker(targets, graph_config, job_id)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(
            lambda s, e, sk: self._on_finished(job_id, s, e, sk))
        self._worker.start()

    def _cancel_send(self):
        if not hasattr(self, "_worker") or not self._worker.isRunning():
            return
        ret = QMessageBox.question(
            self, "送信中止確認",
            "送信を中止しますか？\n未送信の宛先には送信されません。\n"
            "送信済みの分は取り消せません。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if ret != QMessageBox.StandardButton.Yes:
            return
        self._worker.request_cancel()
        self._btn_cancel.setEnabled(False)

    def _on_progress(self, current: int, total: int, message: str):
        self._progress.setValue(current)
        self._progress_label.setText(f"[{current}/{total}] {message}")

    def _on_finished(self, job_id: int, success: int, error: int, skip: int):
        session = get_session()
        try:
            finish_job(session, job_id)
        finally:
            session.close()
        self._btn_send.setEnabled(True)
        self._btn_cancel.setVisible(False)
        self._btn_cancel.setEnabled(True)
        self._progress.setVisible(False)
        QMessageBox.information(
            self, "送信完了",
            f"送信完了\n\n成功: {success} 件\nエラー: {error} 件\nスキップ: {skip} 件\n\n"
            "「送信履歴」タブで詳細を確認できます。"
        )
```

- [ ] **Step 4: テストを実行して成功を確認**

Run: `pytest tests/test_send_worker_cancel.py -v`
Expected: PASS

- [ ] **Step 5: コミット**

```bash
git add app/ui/send_tab.py tests/test_send_worker_cancel.py
git commit -m "feat: 送信タブに中止ボタンを追加"
```

---

## Task 2: 破壊的操作ダイアログの既定ボタンをNoに

**Files:**
- Modify: `app/ui/meeting_tab.py:107-113`, `app/ui/member_tab.py:275-280`, `app/ui/settings_tab.py:177-181`, `app/ui/settings_tab.py:459-464`, `app/ui/template_tab.py:166-169`, `app/ui/dialogs/import_revert_dialog.py:84-92`, `app/ui/send_tab.py:627-630`
- Test: `tests/test_default_button_no.py`（新規）

**Interfaces:**
- Consumes: なし（各箇所は独立した `QMessageBox.question` / `QMessageBox.warning` 呼び出し）

- [ ] **Step 1: 失敗するテストを書く**

```python
# tests/test_default_button_no.py
import pytest
from PyQt6.QtWidgets import QMessageBox


@pytest.fixture
def capture_question(monkeypatch):
    calls = []

    def fake_question(*args, **kwargs):
        calls.append((args, kwargs))
        return QMessageBox.StandardButton.No

    monkeypatch.setattr(QMessageBox, "question", staticmethod(fake_question))
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(fake_question))
    return calls


def _default_button_arg(args, kwargs):
    if "defaultButton" in kwargs:
        return kwargs["defaultButton"]
    return args[4] if len(args) > 4 else None


def test_meeting_delete_defaults_to_no(qtbot, monkeypatch, capture_question):
    monkeypatch.setattr(
        "app.ui.meeting_tab.get_session", lambda: _FakeSession())
    from app.ui.meeting_tab import MeetingTab
    tab = MeetingTab()
    qtbot.addWidget(tab)
    tab._current_meeting_id = 1
    tab._delete_meeting()
    assert capture_question, "QMessageBox.question が呼ばれていない"
    args, kwargs = capture_question[0]
    assert _default_button_arg(args, kwargs) == QMessageBox.StandardButton.No


class _FakeSession:
    def close(self):
        pass
```

- [ ] **Step 2: テストを実行して失敗を確認**

Run: `pytest tests/test_default_button_no.py -v`
Expected: FAIL — `assert None == QMessageBox.StandardButton.No`（`defaultButton` 未指定のため）

- [ ] **Step 3: 各箇所に `defaultButton=QMessageBox.StandardButton.No` を追加**

`app/ui/meeting_tab.py:107-111`:

```python
        ret = QMessageBox.question(
            self, "削除確認",
            f"会議「{self._meeting_combo.currentText()}」を削除しますか？\n"
            "出欠データもすべて削除されます。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
```

`app/ui/member_tab.py:275-279`:

```python
        ret = QMessageBox.question(
            self, "議員退任処理確認",
            "この会員を議員退任処理しますか？\n一覧から非表示になりますが、変更履歴は保持されます。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
```

`app/ui/settings_tab.py:177-179`（署名削除）:

```python
        ret = QMessageBox.question(
            self, "削除確認", "この署名を削除しますか？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
```

`app/ui/settings_tab.py:459-463`（一括削除・開発用）:

```python
        ret = QMessageBox.warning(
            self, "一括削除（開発用）",
            "全会員データを完全に削除します。\nこの操作は取り消せません。\n\n本当に実行しますか？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
```

`app/ui/template_tab.py:166-168`:

```python
        ret = QMessageBox.question(
            self, "削除確認", "このテンプレートを削除しますか？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
```

`app/ui/dialogs/import_revert_dialog.py:84-92`:

```python
        ret = QMessageBox.warning(
            self, "取り消し確認",
            f"以下のインポートを取り消しますか？\n\n"
            f"日時: {dt}\n担当者: {by}\n変更件数: {count}\n\n"
            "・インポートで新規追加された会員は削除されます\n"
            "・インポートで更新された会員は変更前の状態に戻ります\n\n"
            "この操作は元に戻せません。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
```

`app/ui/send_tab.py:627-629`（送信確認。送信も取り消せない操作のため統一）:

```python
        ret = QMessageBox.question(
            self, "送信確認", msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
```

- [ ] **Step 4: テストを実行して成功を確認**

Run: `pytest tests/test_default_button_no.py -v`
Expected: PASS

- [ ] **Step 5: コミット**

```bash
git add app/ui/meeting_tab.py app/ui/member_tab.py app/ui/settings_tab.py \
        app/ui/template_tab.py app/ui/dialogs/import_revert_dialog.py app/ui/send_tab.py \
        tests/test_default_button_no.py
git commit -m "fix: 破壊的操作の確認ダイアログの既定ボタンをNoに変更"
```

---

## Task 3: テンプレート編集の未保存変更警告

**Files:**
- Modify: `app/ui/template_tab.py:21-137`
- Test: `tests/test_template_tab_unsaved.py`（新規）

**Interfaces:**
- Consumes: なし
- Produces: `TemplateTab._is_dirty() -> bool`, `TemplateTab._confirm_discard() -> bool`

- [ ] **Step 1: 失敗するテストを書く**

```python
# tests/test_template_tab_unsaved.py
import pytest
from PyQt6.QtWidgets import QMessageBox


def test_selecting_other_template_prompts_when_dirty(qtbot, monkeypatch):
    monkeypatch.setattr(
        "app.ui.template_tab.get_session", lambda: _FakeSession())
    monkeypatch.setattr("app.ui.template_tab.get_templates", lambda s: [])
    monkeypatch.setattr("app.ui.template_tab.get_signatures", lambda s: [])

    from app.ui.template_tab import TemplateTab
    tab = TemplateTab()
    qtbot.addWidget(tab)

    tab._name.setText("新しい名前")  # 未保存の変更を作る
    assert tab._is_dirty() is True

    calls = []
    monkeypatch.setattr(
        QMessageBox, "question",
        staticmethod(lambda *a, **k: (calls.append((a, k)),
                                       QMessageBox.StandardButton.No)[1]))
    assert tab._confirm_discard() is False
    assert calls, "未保存確認ダイアログが表示されていない"


class _FakeSession:
    def close(self):
        pass
```

- [ ] **Step 2: テストを実行して失敗を確認**

Run: `pytest tests/test_template_tab_unsaved.py -v`
Expected: FAIL — `AttributeError: 'TemplateTab' object has no attribute '_is_dirty'`

- [ ] **Step 3: 未保存判定と確認ダイアログを実装**

`app/ui/template_tab.py:21-26` の `__init__` を以下に置き換える:

```python
class TemplateTab(QWidget):
    def __init__(self):
        super().__init__()
        self._current_id: int | None = None
        self._snapshot: tuple = ("", "", "", None)
        self._build()
        self._load()
```

`app/ui/template_tab.py:113-136`（`_on_select` 〜 `_new`）を以下に置き換える:

```python
    def _on_select(self, row: int):
        if row < 0 or row >= len(self._templates):
            return
        if not self._confirm_discard():
            self._list.blockSignals(True)
            self._select_row_for_id(self._current_id)
            self._list.blockSignals(False)
            return
        t = self._templates[row]
        self._current_id = t.id
        self._name.setText(t.name)
        self._subject.setText(t.subject)
        self._body.setPlainText(t.body)
        for i in range(self._sig_combo.count()):
            if self._sig_combo.itemData(i) == t.signature_id:
                self._sig_combo.setCurrentIndex(i)
                break
        self._take_snapshot()

    def _select_row_for_id(self, template_id: int | None):
        for i, t in enumerate(self._templates):
            if t.id == template_id:
                self._list.setCurrentRow(i)
                return
        self._list.clearSelection()

    def _take_snapshot(self):
        self._snapshot = (
            self._name.text(), self._subject.text(),
            self._body.toPlainText(), self._sig_combo.currentData())

    def _is_dirty(self) -> bool:
        current = (
            self._name.text(), self._subject.text(),
            self._body.toPlainText(), self._sig_combo.currentData())
        return current != self._snapshot

    def _confirm_discard(self) -> bool:
        if not self._is_dirty():
            return True
        ret = QMessageBox.question(
            self, "未保存の変更",
            "編集中の内容が保存されていません。破棄しますか？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        return ret == QMessageBox.StandardButton.Yes

    def _insert_placeholder(self, placeholder: str):
        self._body.setFocus()
        self._body.insertPlainText(placeholder)

    def _new(self):
        if not self._confirm_discard():
            return
        self._current_id = None
        self._name.clear()
        self._subject.clear()
        self._body.clear()
        self._sig_combo.setCurrentIndex(0)
        self._list.clearSelection()
        self._take_snapshot()
```

最後に `_save` の末尾（`app/ui/template_tab.py:160-161` 相当）で `self._load()` の直後に `self._take_snapshot()` を呼ぶよう1行追加する:

```python
        QMessageBox.information(self, "保存", "テンプレートを保存しました。")
        self._load()
        self._take_snapshot()
```

- [ ] **Step 4: テストを実行して成功を確認**

Run: `pytest tests/test_template_tab_unsaved.py -v`
Expected: PASS

- [ ] **Step 5: コミット**

```bash
git add app/ui/template_tab.py tests/test_template_tab_unsaved.py
git commit -m "feat: テンプレート編集に未保存変更の確認を追加"
```

---

## Task 4: 会員編集ダイアログの未保存変更警告

**Files:**
- Modify: `app/ui/dialogs/member_edit_dialog.py:17-129`
- Test: `tests/test_member_edit_dialog_unsaved.py`（新規）

**Interfaces:**
- Consumes: `Task 3` の `_is_dirty` パターンを踏襲（実装は独立）
- Produces: `MemberEditDialog._is_dirty() -> bool`, `MemberEditDialog.reject()` オーバーライド

- [ ] **Step 1: 失敗するテストを書く**

```python
# tests/test_member_edit_dialog_unsaved.py
import pytest
from PyQt6.QtWidgets import QDialog, QMessageBox


def test_reject_prompts_when_dirty(qtbot, db_session, monkeypatch):
    from app.ui.dialogs.member_edit_dialog import MemberEditDialog
    dlg = MemberEditDialog(db_session, staff_name="担当者A")
    qtbot.addWidget(dlg)

    dlg._org_name.setText("テスト事業所")  # 未保存の変更を作る
    assert dlg._is_dirty() is True

    question_calls = []
    monkeypatch.setattr(
        QMessageBox, "question",
        staticmethod(lambda *a, **k: (question_calls.append((a, k)),
                                       QMessageBox.StandardButton.No)[1]))
    super_reject_calls = []
    monkeypatch.setattr(QDialog, "reject", lambda self: super_reject_calls.append(True))

    dlg.reject()
    assert question_calls, "未保存確認ダイアログが表示されていない"
    assert super_reject_calls == [], "破棄しないと回答した場合はダイアログを閉じてはならない"
```

- [ ] **Step 2: テストを実行して失敗を確認**

Run: `pytest tests/test_member_edit_dialog_unsaved.py -v`
Expected: FAIL — `AttributeError: 'MemberEditDialog' object has no attribute '_is_dirty'`

- [ ] **Step 3: 未保存判定と `reject()` オーバーライドを実装**

`app/ui/dialogs/member_edit_dialog.py:17-30`（`__init__`）を以下に置き換える:

```python
class MemberEditDialog(QDialog):
    def __init__(self, session: Session, member: Member | None = None,
                 staff_name: str = "", parent=None):
        super().__init__(parent)
        self._session = session
        self._member = member
        self._staff_name = staff_name
        self._photo_path: str | None = None
        self._photo_deleted: bool = False
        self._snapshot: tuple = ()
        self.setWindowTitle("会員編集" if member else "会員追加")
        self.setMinimumWidth(520)
        self._build()
        if member:
            self._load(member)
        self._take_snapshot()
```

`app/ui/dialogs/member_edit_dialog.py:236-245`（`_save` 末尾）の直前、`self.accept()` の前に変更はないが、`_save` の直後に呼ばれる保存成功時は素直に `accept()` すればよい（既存のまま）。

新たに `_take_snapshot` / `_is_dirty` / `reject` を `_save` メソッドの直後に追加する:

```python
    def _current_state(self) -> tuple:
        emails = tuple(
            (a.text().strip(), l.text().strip()) for a, l in self._email_rows)
        return (
            self._member_number.text().strip(),
            self._org_name.text().strip(),
            self._org_kana.text().strip(),
            self._title.text().strip(),
            self._name.text().strip(),
            self._name_kana.text().strip(),
            self._notes.text().strip(),
            self._position_combo.currentData(),
            emails,
        )

    def _take_snapshot(self):
        self._snapshot = self._current_state()

    def _is_dirty(self) -> bool:
        return self._current_state() != self._snapshot

    def reject(self):
        if self._is_dirty():
            ret = QMessageBox.question(
                self, "未保存の変更",
                "入力内容が保存されていません。破棄しますか？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No)
            if ret != QMessageBox.StandardButton.Yes:
                return
        super().reject()
```

- [ ] **Step 4: テストを実行して成功を確認**

Run: `pytest tests/test_member_edit_dialog_unsaved.py -v`
Expected: PASS

- [ ] **Step 5: コミット**

```bash
git add app/ui/dialogs/member_edit_dialog.py tests/test_member_edit_dialog_unsaved.py
git commit -m "feat: 会員編集ダイアログに未保存変更の確認を追加"
```

---

## Task 5: 署名本文をQTextEditに変更

**Files:**
- Modify: `app/ui/settings_tab.py:83-194`（`_SignatureWidget`）
- Test: `tests/test_signature_widget_textedit.py`（新規）

**Interfaces:**
- Consumes: `get_signatures`, `create_signature`, `update_signature`, `delete_signature`, `set_default`（signature_service.py、変更なし）

- [ ] **Step 1: 失敗するテストを書く**

```python
# tests/test_signature_widget_textedit.py
from PyQt6.QtWidgets import QTextEdit


def test_body_field_is_textedit_and_preserves_newlines(qtbot, monkeypatch):
    monkeypatch.setattr(
        "app.ui.settings_tab.get_session", lambda: _FakeSession())
    monkeypatch.setattr("app.ui.settings_tab.get_signatures", lambda s: [])

    from app.ui.settings_tab import _SignatureWidget
    w = _SignatureWidget()
    qtbot.addWidget(w)

    assert isinstance(w._body, QTextEdit)
    w._body.setPlainText("1行目\n2行目\n3行目")
    assert w._body.toPlainText() == "1行目\n2行目\n3行目"


class _FakeSession:
    def close(self):
        pass
```

- [ ] **Step 2: テストを実行して失敗を確認**

Run: `pytest tests/test_signature_widget_textedit.py -v`
Expected: FAIL — `assert isinstance(w._body, QTextEdit)` で `AttributeError` または `False`（現状は `QLineEdit`）

- [ ] **Step 3: `_SignatureWidget` を `QTextEdit` ベースに変更**

`app/ui/settings_tab.py:1-7` のimportに `QTextEdit` を追加:

```python
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QTabWidget, QFormLayout, QHBoxLayout,
    QLineEdit, QPushButton, QGroupBox, QTableWidget, QTableWidgetItem,
    QCheckBox, QMessageBox, QHeaderView, QLabel, QRadioButton, QButtonGroup,
    QFileDialog, QInputDialog, QTextEdit,
)
```

`app/ui/settings_tab.py:95-101`（フォーム部分）を以下に置き換える:

```python
        form = QFormLayout()
        self._name = QLineEdit()
        self._body = QTextEdit()
        self._body.setPlaceholderText("署名本文（複数行入力可）")
        self._body.setMaximumHeight(140)
        form.addRow("署名名", self._name)
        form.addRow("本文", self._body)
        layout.addLayout(form)
```

`app/ui/settings_tab.py:134-140`（`_on_select`）を以下に置き換える（`\n` エスケープの往復変換を廃止）:

```python
    def _on_select(self):
        row = self._table.currentRow()
        if row < 0 or row >= len(self._signatures):
            return
        s = self._signatures[row]
        self._name.setText(s.name)
        self._body.setPlainText(s.body)
```

`app/ui/settings_tab.py:148-171`（`_add` / `_update`）内の `body = self._body.text().replace("\\n", "\n")` を `body = self._body.toPlainText()` に変更する（2箇所）:

```python
    def _add(self):
        name = self._name.text().strip()
        body = self._body.toPlainText()
        if not name:
            QMessageBox.warning(self, "入力エラー", "署名名を入力してください。")
            return
        session = get_session()
        create_signature(session, name, body)
        session.close()
        self._load()

    def _update(self):
        sig_id = self._selected_id()
        if sig_id is None:
            return
        name = self._name.text().strip()
        body = self._body.toPlainText()
        if not name:
            QMessageBox.warning(self, "入力エラー", "署名名を入力してください。")
            return
        session = get_session()
        update_signature(session, sig_id, name=name, body=body)
        session.close()
        self._load()
```

- [ ] **Step 4: テストを実行して成功を確認**

Run: `pytest tests/test_signature_widget_textedit.py -v`
Expected: PASS

- [ ] **Step 5: コミット**

```bash
git add app/ui/settings_tab.py tests/test_signature_widget_textedit.py
git commit -m "feat: 署名本文の入力欄をQTextEditに変更し複数行入力を可能にする"
```

---

## Task 6: 送信履歴タブ・名簿タブの自動更新

**Files:**
- Modify: `app/ui/history_tab.py:12-18`, `app/ui/member_tab.py:14-19`
- Test: `tests/test_tab_refresh.py`（新規）

**Interfaces:**
- Consumes: `MainWindow._on_tab_change`（既存: `hasattr(widget, "refresh")` で呼び出す。変更不要）

- [ ] **Step 1: 失敗するテストを書く**

```python
# tests/test_tab_refresh.py
def test_history_tab_has_refresh(qtbot, monkeypatch):
    monkeypatch.setattr("app.ui.history_tab.get_session", lambda: _FakeSession())
    monkeypatch.setattr("app.ui.history_tab.get_jobs", lambda s: [])

    from app.ui.history_tab import HistoryTab
    tab = HistoryTab()
    qtbot.addWidget(tab)
    assert hasattr(tab, "refresh")
    tab.refresh()  # 例外なく再読込できること


def test_member_tab_has_refresh(qtbot, monkeypatch):
    monkeypatch.setattr("app.ui.member_tab.get_session", lambda: _FakeSession())
    monkeypatch.setattr("app.ui.member_tab.get_members", lambda *a, **k: [])

    from app.ui.member_tab import MemberTab
    tab = MemberTab()
    qtbot.addWidget(tab)
    assert hasattr(tab, "refresh")
    tab.refresh()


class _FakeSession:
    def close(self):
        pass
```

- [ ] **Step 2: テストを実行して失敗を確認**

Run: `pytest tests/test_tab_refresh.py -v`
Expected: FAIL — `assert hasattr(tab, "refresh")`（`HistoryTab` / `MemberTab` に `refresh` が存在しない）

- [ ] **Step 3: `refresh` メソッドを追加**

`app/ui/history_tab.py:17-18`（`_build()` 呼び出しの直後）に1行追加:

```python
        self._build()
        self._load_jobs()

    def refresh(self):
        self._load_jobs()
```

`app/ui/member_tab.py:18-19`（`_build()` 呼び出しの直後）に1行追加:

```python
        self._build()
        self._load()

    def refresh(self):
        self._load()
```

- [ ] **Step 4: テストを実行して成功を確認**

Run: `pytest tests/test_tab_refresh.py -v`
Expected: PASS

- [ ] **Step 5: コミット**

```bash
git add app/ui/history_tab.py app/ui/member_tab.py tests/test_tab_refresh.py
git commit -m "fix: 送信履歴タブ・名簿タブがタブ切替時に自動更新されるようにする"
```

---

## Task 7: 宛先一覧の「表示中を全選択/全解除」

**Files:**
- Modify: `app/ui/recipient_panel.py:92-120`（`_build`）
- Test: `tests/test_recipient_panel_select_all.py`（新規）

**Interfaces:**
- Produces: `RecipientPanel.select_all_visible()`, `RecipientPanel.clear_visible()`

- [ ] **Step 1: 失敗するテストを書く**

```python
# tests/test_recipient_panel_select_all.py
from app.ui.recipient_panel import RecipientPanel


class _Member:
    def __init__(self, id, org_name):
        self.id = id
        self.member_number = f"A-{id:03d}"
        self.organization_name = org_name
        self.organization_kana = ""
        self.name = "テスト太郎"
        self.name_kana = ""
        self.title = ""
        self.position = None
        self.email_addresses = []


def test_select_all_visible_only_checks_unhidden_rows(qtbot):
    panel = RecipientPanel()
    qtbot.addWidget(panel)
    panel.load_members([_Member(1, "対象商事"), _Member(2, "除外商事")])

    panel.filter("対象")  # 除外商事の行を非表示にする
    panel.select_all_visible()

    checked_orgs = [m.organization_name for m in panel.get_selected_members()]
    assert checked_orgs == ["対象商事"]


def test_clear_visible_unchecks_only_visible_rows(qtbot):
    panel = RecipientPanel()
    qtbot.addWidget(panel)
    panel.load_members([_Member(1, "対象商事"), _Member(2, "除外商事")])
    panel.set_checks_by_member_ids({1, 2})

    panel.filter("対象")
    panel.clear_visible()

    checked_orgs = {m.organization_name for m in panel.get_selected_members()}
    assert checked_orgs == {"除外商事"}
```

- [ ] **Step 2: テストを実行して失敗を確認**

Run: `pytest tests/test_recipient_panel_select_all.py -v`
Expected: FAIL — `AttributeError: 'RecipientPanel' object has no attribute 'select_all_visible'`

- [ ] **Step 3: 全選択/全解除ボタンを実装**

`app/ui/recipient_panel.py:104-120`（`search_row` 部分）を以下に置き換える:

```python
        search_row = QHBoxLayout()
        self._search = QLineEdit()
        self._search.setPlaceholderText("絞り込み（会員番号・事業所名・氏名）")
        self._search.textChanged.connect(
            lambda text: self.filter(text))
        search_row.addWidget(self._search)
        btn_select_all = QPushButton("表示中を全選択")
        btn_select_all.clicked.connect(self.select_all_visible)
        btn_clear_visible = QPushButton("表示中を全解除")
        btn_clear_visible.clicked.connect(self.clear_visible)
        search_row.addWidget(btn_select_all)
        search_row.addWidget(btn_clear_visible)
        btn_fd = QPushButton("A-")
        btn_fd.setFixedWidth(36)
        btn_fd.setToolTip("文字を小さくする")
        btn_fd.clicked.connect(lambda: self._adjust_font(-1))
        btn_fu = QPushButton("A+")
        btn_fu.setFixedWidth(36)
        btn_fu.setToolTip("文字を大きくする")
        btn_fu.clicked.connect(lambda: self._adjust_font(1))
        search_row.addWidget(btn_fd)
        search_row.addWidget(btn_fu)
        layout.addLayout(search_row)
```

続けて、`clear_checks` メソッド（`app/ui/recipient_panel.py:66-75`）の直後に新メソッドを追加する:

```python
    def select_all_visible(self):
        self._table.setUpdatesEnabled(False)
        for row in range(self._table.rowCount()):
            if self._table.isRowHidden(row):
                continue
            cb = self._table.cellWidget(row, 0)
            if cb:
                cb.blockSignals(True)
                cb.setChecked(True)
                cb.blockSignals(False)
        self._table.setUpdatesEnabled(True)
        self._update_count()

    def clear_visible(self):
        self._table.setUpdatesEnabled(False)
        for row in range(self._table.rowCount()):
            if self._table.isRowHidden(row):
                continue
            cb = self._table.cellWidget(row, 0)
            if cb:
                cb.blockSignals(True)
                cb.setChecked(False)
                cb.blockSignals(False)
        self._table.setUpdatesEnabled(True)
        self._update_count()
```

- [ ] **Step 4: テストを実行して成功を確認**

Run: `pytest tests/test_recipient_panel_select_all.py -v`
Expected: PASS

- [ ] **Step 5: コミット**

```bash
git add app/ui/recipient_panel.py tests/test_recipient_panel_select_all.py
git commit -m "feat: 宛先一覧に表示中を全選択/全解除するボタンを追加"
```

---

## Task 8: 保存完了メッセージをインライン表示に

**Files:**
- Create: `app/ui/widgets/inline_status.py`
- Modify: `app/ui/settings_tab.py:32-81`（`_GraphSettingsWidget`）, `app/ui/settings_tab.py:370-421`（`_ExportSettingsWidget`）, `app/ui/template_tab.py:82-84, 138-161`
- Test: `tests/test_inline_status.py`（新規）

**Interfaces:**
- Produces: `show_inline_message(label: QLabel, text: str, ms: int = 2500) -> None`

- [ ] **Step 1: 失敗するテストを書く**

```python
# tests/test_inline_status.py
from PyQt6.QtWidgets import QLabel


def test_show_inline_message_sets_text_and_clears_after_timeout(qtbot):
    from app.ui.widgets.inline_status import show_inline_message
    label = QLabel()
    qtbot.addWidget(label)

    show_inline_message(label, "保存しました", ms=100)
    assert label.text() == "保存しました"

    qtbot.waitUntil(lambda: label.text() == "", timeout=1000)
```

- [ ] **Step 2: テストを実行して失敗を確認**

Run: `pytest tests/test_inline_status.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.ui.widgets'`

- [ ] **Step 3: `inline_status.py` を実装し、既存の保存完了ダイアログを置き換える**

`app/ui/widgets/__init__.py`（新規、空ファイル）:

```python
```

`app/ui/widgets/inline_status.py`（新規）:

```python
from PyQt6.QtWidgets import QLabel
from PyQt6.QtCore import QTimer


def show_inline_message(label: QLabel, text: str, ms: int = 2500) -> None:
    label.setText(text)
    label.setStyleSheet("color: #16A34A;")
    QTimer.singleShot(ms, lambda: label.setText(""))
```

`app/ui/settings_tab.py:32-55`（`_GraphSettingsWidget.__init__`）を以下に置き換える:

```python
class _GraphSettingsWidget(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        grp = QGroupBox("Microsoft 365 / Graph API 設定")
        form = QFormLayout(grp)
        self._tenant_id = QLineEdit()
        self._client_id = QLineEdit()
        self._test_address = QLineEdit()
        form.addRow("テナントID", self._tenant_id)
        form.addRow("クライアントID", self._client_id)
        form.addRow("テスト送信先", self._test_address)
        layout.addWidget(grp)
        btn_row = QHBoxLayout()
        btn_save = QPushButton("設定を保存")
        btn_save.clicked.connect(self._save)
        btn_test = QPushButton("接続テスト")
        btn_test.clicked.connect(self._test_connection)
        btn_row.addWidget(btn_save)
        btn_row.addWidget(btn_test)
        btn_row.addStretch()
        layout.addLayout(btn_row)
        self._status_label = QLabel("")
        layout.addWidget(self._status_label)
        layout.addStretch()
        self._load()
```

`app/ui/settings_tab.py:63-71`（`_save`）を以下に置き換える:

```python
    def _save(self):
        config = get_config()
        config["graph"] = {
            "tenant_id":  self._tenant_id.text().strip(),
            "client_id":  self._client_id.text().strip(),
            "test_address": self._test_address.text().strip(),
        }
        save_config(config)
        from app.ui.widgets.inline_status import show_inline_message
        show_inline_message(self._status_label, "設定を保存しました")
```

`app/ui/settings_tab.py:372-404`（`_ExportSettingsWidget.__init__`）の `btn_row` 直後（`layout.addStretch()` の前）に `self._status_label` を追加:

```python
        btn_row = QHBoxLayout()
        btn_save = QPushButton("設定を保存")
        btn_save.clicked.connect(self._save)
        btn_export = QPushButton("今すぐ出力")
        btn_export.clicked.connect(self._export_now)
        btn_row.addWidget(btn_save)
        btn_row.addWidget(btn_export)
        btn_row.addStretch()
        layout.addLayout(btn_row)
        self._status_label = QLabel("")
        layout.addWidget(self._status_label)
        layout.addStretch()
        self._load()
```

`app/ui/settings_tab.py:416-420`（`_ExportSettingsWidget._save`）を以下に置き換える:

```python
    def _save(self):
        config = get_config()
        config["html_export_path"] = self._path_edit.text().strip()
        save_config(config)
        from app.ui.widgets.inline_status import show_inline_message
        show_inline_message(self._status_label, "設定を保存しました")
```

`app/ui/template_tab.py:52-63`（`right_layout` 構築部分）の `btn_save` の後にステータスラベルを追加:

```python
        btn_save = QPushButton("保存")
        btn_save.clicked.connect(self._save)
        right_layout.addWidget(btn_save)
        self._status_label = QLabel("")
        right_layout.addWidget(self._status_label)
        splitter.addWidget(right)
```

`app/ui/template_tab.py:138-161`（`_save`）の `QMessageBox.information(self, "保存", "テンプレートを保存しました。")` の行を以下に置き換える:

```python
        from app.ui.widgets.inline_status import show_inline_message
        show_inline_message(self._status_label, "テンプレートを保存しました")
        self._load()
        self._take_snapshot()
```

（Task 3 実装済みの場合、`_take_snapshot()` はそのまま残す。Task 3 未実装の場合は `self._load()` のみでよい。）

- [ ] **Step 4: テストを実行して成功を確認**

Run: `pytest tests/test_inline_status.py -v`
Expected: PASS

- [ ] **Step 5: コミット**

```bash
git add app/ui/widgets/__init__.py app/ui/widgets/inline_status.py \
        app/ui/settings_tab.py app/ui/template_tab.py tests/test_inline_status.py
git commit -m "feat: 頻繁な保存操作の完了通知をモーダルからインライン表示に変更"
```

---

## Task 9: インポートダイアログにデータプレビュー

**Files:**
- Modify: `app/ui/dialogs/import_dialog.py:1-94`
- Test: `tests/test_import_dialog_preview.py`（新規）

**Interfaces:**
- Consumes: `load_member_file(path) -> (headers, rows)`（import_service.py、変更なし）

- [ ] **Step 1: 失敗するテストを書く**

```python
# tests/test_import_dialog_preview.py
def test_browse_populates_preview_table(qtbot, db_session, monkeypatch, tmp_path):
    headers = ["会員番号", "事業所名"]
    rows = [["A-001", "○○商事"], ["A-002", "△△産業"], ["A-003", "□□工業"]]
    monkeypatch.setattr(
        "app.ui.dialogs.import_dialog.load_member_file",
        lambda path: (headers, rows))

    from app.ui.dialogs.import_dialog import ImportDialog
    dlg = ImportDialog(db_session)
    qtbot.addWidget(dlg)
    dlg._on_file_loaded("dummy.xlsx", headers, rows)

    assert dlg._preview_table.columnCount() == 2
    assert dlg._preview_table.rowCount() == 3  # 先頭3行のみ表示
    assert dlg._preview_table.item(0, 0).text() == "A-001"
```

- [ ] **Step 2: テストを実行して失敗を確認**

Run: `pytest tests/test_import_dialog_preview.py -v`
Expected: FAIL — `AttributeError: 'ImportDialog' object has no attribute '_on_file_loaded'`

- [ ] **Step 3: プレビューテーブルを追加**

`app/ui/dialogs/import_dialog.py:2-6` のimportに `QTableWidget, QTableWidgetItem, QHeaderView` を追加（既にimport済み）。

`app/ui/dialogs/import_dialog.py:42-65`（`_build`）を以下に置き換える:

```python
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

        # データプレビュー（先頭5行）
        preview_grp = QGroupBox("データプレビュー（先頭5行）")
        preview_layout = QVBoxLayout(preview_grp)
        self._preview_table = QTableWidget(0, 0)
        self._preview_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._preview_table.setMaximumHeight(160)
        preview_layout.addWidget(self._preview_table)
        self._row_count_label = QLabel("")
        preview_layout.addWidget(self._row_count_label)
        layout.addWidget(preview_grp)

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
```

`app/ui/dialogs/import_dialog.py:79-94`（`_browse`）を以下に置き換える:

```python
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
        self._on_file_loaded(path, headers, rows)

    def _on_file_loaded(self, path: str, headers: list[str], rows: list[list]):
        self._file_path.setText(path)
        self._headers = headers
        self._rows = rows
        self._populate_combos(headers)
        self._populate_preview(headers, rows)
        self._btn_import.setEnabled(True)

    def _populate_preview(self, headers: list[str], rows: list[list]):
        self._preview_table.setColumnCount(len(headers))
        self._preview_table.setHorizontalHeaderLabels(headers)
        preview_rows = rows[:5]
        self._preview_table.setRowCount(len(preview_rows))
        for r, row in enumerate(preview_rows):
            for c, value in enumerate(row):
                self._preview_table.setItem(r, c, QTableWidgetItem(str(value)))
        self._preview_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch)
        self._row_count_label.setText(f"全 {len(rows)} 件中 先頭{len(preview_rows)}件を表示")
```

- [ ] **Step 4: テストを実行して成功を確認**

Run: `pytest tests/test_import_dialog_preview.py -v`
Expected: PASS

- [ ] **Step 5: コミット**

```bash
git add app/ui/dialogs/import_dialog.py tests/test_import_dialog_preview.py
git commit -m "feat: インポートダイアログにデータプレビューを追加"
```

---

## Task 10: 名簿タブに編集系ボタンをツールバーに追加

**Files:**
- Modify: `app/ui/member_tab.py:24-114`（`_build`）
- Test: `tests/test_member_tab_toolbar_buttons.py`（新規）

**Interfaces:**
- Consumes: 既存の `_edit`, `_show_history`, `_delete`（変更なし）

- [ ] **Step 1: 失敗するテストを書く**

```python
# tests/test_member_tab_toolbar_buttons.py
def test_edit_buttons_disabled_until_row_selected(qtbot, monkeypatch):
    monkeypatch.setattr("app.ui.member_tab.get_session", lambda: _FakeSession())
    monkeypatch.setattr("app.ui.member_tab.get_members", lambda *a, **k: [_Member()])

    from app.ui.member_tab import MemberTab
    tab = MemberTab()
    qtbot.addWidget(tab)

    assert tab._btn_edit.isEnabled() is False
    assert tab._btn_history.isEnabled() is False
    assert tab._btn_retire.isEnabled() is False

    tab._table.selectRow(0)
    assert tab._btn_edit.isEnabled() is True
    assert tab._btn_history.isEnabled() is True
    assert tab._btn_retire.isEnabled() is True


class _Member:
    def __init__(self):
        self.id = 1
        self.member_number = "A-001"
        self.organization_name = "テスト商事"
        self.organization_kana = ""
        self.name = "山田太郎"
        self.name_kana = ""
        self.title = ""
        self.position = None
        self.email_addresses = []
        self.is_active = True
        self.updated_at = None
        self.photo_thumb = None


class _FakeSession:
    def close(self):
        pass
```

- [ ] **Step 2: テストを実行して失敗を確認**

Run: `pytest tests/test_member_tab_toolbar_buttons.py -v`
Expected: FAIL — `AttributeError: 'MemberTab' object has no attribute '_btn_edit'`

- [ ] **Step 3: ツールバーに編集系ボタンを追加**

`app/ui/member_tab.py:44-64`（ツールバー2行目）を以下に置き換える:

```python
        # ツールバー 2行目：操作ボタン
        row2 = QHBoxLayout()
        btn_add = QPushButton("追加")
        btn_add.clicked.connect(self._add)

        self._btn_edit = QPushButton("編集")
        self._btn_edit.setEnabled(False)
        self._btn_edit.clicked.connect(self._edit)
        self._btn_history = QPushButton("変更履歴")
        self._btn_history.setEnabled(False)
        self._btn_history.clicked.connect(self._show_history)
        self._btn_retire = QPushButton("議員退任")
        self._btn_retire.setEnabled(False)
        self._btn_retire.clicked.connect(self._delete)

        btn_file = QPushButton("ファイル")
        file_menu = QMenu(btn_file)
        file_menu.addAction("インポート", self._import)
        file_menu.addAction("インポート取り消し", self._import_revert)
        file_menu.addSeparator()
        file_menu.addAction("エクスポート", self._export)
        btn_file.setMenu(file_menu)

        btn_order = QPushButton("順番設定")
        btn_order.clicked.connect(self._order_settings)

        row2.addWidget(btn_add)
        row2.addWidget(self._btn_edit)
        row2.addWidget(self._btn_history)
        row2.addWidget(self._btn_retire)
        row2.addWidget(btn_file)
        row2.addWidget(btn_order)
        row2.addStretch()
        layout.addLayout(row2)
```

`app/ui/member_tab.py:96-98`（テーブル選択シグナル接続部分）に選択変更ハンドラを追加:

```python
        self._table.doubleClicked.connect(self._edit)
        self._table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._table.customContextMenuRequested.connect(self._show_context_menu)
        self._table.itemSelectionChanged.connect(self._on_selection_changed)
```

`_load` メソッド（`app/ui/member_tab.py:144-217`）の末尾、`finally: session.close()` の直後に選択状態のリセットを追加する形で、新たに `_on_selection_changed` を `_selected_member_id` の直前（`app/ui/member_tab.py:219`付近）に追加:

```python
    def _on_selection_changed(self):
        has_selection = self._table.currentRow() >= 0
        self._btn_edit.setEnabled(has_selection)
        self._btn_history.setEnabled(has_selection)
        self._btn_retire.setEnabled(has_selection)
```

`_load()` の最後（`app/ui/member_tab.py:216`、`finally` の直前）に1行追加してロード直後もボタン状態を同期する:

```python
        finally:
            session.close()
        self._on_selection_changed()
```

- [ ] **Step 4: テストを実行して成功を確認**

Run: `pytest tests/test_member_tab_toolbar_buttons.py -v`
Expected: PASS

- [ ] **Step 5: コミット**

```bash
git add app/ui/member_tab.py tests/test_member_tab_toolbar_buttons.py
git commit -m "feat: 名簿タブのツールバーに編集・変更履歴・議員退任ボタンを追加"
```

---

## Task 11: 送信タブ本文欄の高さ緩和

**Files:**
- Modify: `app/ui/send_tab.py:175-188`（`_build_step2`）
- Test: `tests/test_send_tab_body_height.py`（新規）

**Interfaces:**
- Consumes: なし

- [ ] **Step 1: 失敗するテストを書く**

```python
# tests/test_send_tab_body_height.py
def test_body_edit_has_expand_button(qtbot, monkeypatch):
    monkeypatch.setattr("app.ui.send_tab.get_session", lambda: _FakeSession())
    monkeypatch.setattr("app.ui.send_tab.get_positions", lambda s: [])
    monkeypatch.setattr("app.ui.send_tab.get_members", lambda s: [])
    monkeypatch.setattr("app.ui.send_tab.get_templates", lambda s: [])
    monkeypatch.setattr("app.ui.send_tab.get_signatures", lambda s: [])
    monkeypatch.setattr("app.ui.send_tab.get_default_signature", lambda s: None)

    from app.ui.send_tab import SendTab
    tab = SendTab()
    qtbot.addWidget(tab)

    assert tab._body_edit.maximumHeight() >= 240
    assert hasattr(tab, "_btn_expand_body")


class _FakeSession:
    def close(self):
        pass
```

- [ ] **Step 2: テストを実行して失敗を確認**

Run: `pytest tests/test_send_tab_body_height.py -v`
Expected: FAIL — `assert 120 >= 240`

- [ ] **Step 3: 本文欄の高さを緩和し拡大表示ボタンを追加**

`app/ui/send_tab.py:175-188`（`_build_step2`）を以下に置き換える:

```python
    def _build_step2(self) -> QGroupBox:
        grp = QGroupBox("Step 2：テンプレート・署名選択")
        f = QFormLayout(grp)
        self._template_combo = QComboBox()
        self._template_combo.currentIndexChanged.connect(self._on_template_select)
        self._sig_combo = QComboBox()
        self._subject_edit = QLineEdit()
        self._body_edit = QTextEdit()
        self._body_edit.setMinimumHeight(200)
        self._body_edit.setMaximumHeight(280)
        self._btn_expand_body = QPushButton("本文を拡大して編集")
        self._btn_expand_body.clicked.connect(self._expand_body_edit)
        f.addRow("テンプレート", self._template_combo)
        f.addRow("署名", self._sig_combo)
        f.addRow("件名", self._subject_edit)
        f.addRow("本文", self._body_edit)
        f.addRow("", self._btn_expand_body)
        return grp

    def _expand_body_edit(self):
        from PyQt6.QtWidgets import QDialog, QVBoxLayout as _QVBoxLayout
        dlg = QDialog(self)
        dlg.setWindowTitle("本文編集")
        dlg.resize(700, 600)
        layout = _QVBoxLayout(dlg)
        editor = QTextEdit()
        editor.setPlainText(self._body_edit.toPlainText())
        layout.addWidget(editor)
        btn_row = QHBoxLayout()
        btn_ok = QPushButton("反映して閉じる")
        btn_ok.clicked.connect(dlg.accept)
        btn_row.addStretch()
        btn_row.addWidget(btn_ok)
        layout.addLayout(btn_row)
        if dlg.exec():
            self._body_edit.setPlainText(editor.toPlainText())
```

- [ ] **Step 4: テストを実行して成功を確認**

Run: `pytest tests/test_send_tab_body_height.py -v`
Expected: PASS

- [ ] **Step 5: コミット**

```bash
git add app/ui/send_tab.py tests/test_send_tab_body_height.py
git commit -m "feat: 送信タブの本文欄を拡大表示できるようにする"
```

---

## Task 12: 一括削除機能を開発者向けフラグで隠す

**Files:**
- Modify: `app/ui/settings_tab.py:18-29`（`SettingsTab.__init__`）
- Test: `tests/test_data_widget_hidden.py`（新規）

**Interfaces:**
- Consumes: 環境変数 `CCI_MAIL_DEV_TOOLS`

- [ ] **Step 1: 失敗するテストを書く**

```python
# tests/test_data_widget_hidden.py
import os


def test_data_tab_hidden_by_default(qtbot, monkeypatch):
    monkeypatch.delenv("CCI_MAIL_DEV_TOOLS", raising=False)
    from app.ui.settings_tab import SettingsTab
    tab = SettingsTab()
    qtbot.addWidget(tab)
    inner = tab.findChild(__import__("PyQt6.QtWidgets", fromlist=["QTabWidget"]).QTabWidget)
    labels = [inner.tabText(i) for i in range(inner.count())]
    assert "データ管理" not in labels


def test_data_tab_visible_with_env_flag(qtbot, monkeypatch):
    monkeypatch.setenv("CCI_MAIL_DEV_TOOLS", "1")
    from app.ui.settings_tab import SettingsTab
    tab = SettingsTab()
    qtbot.addWidget(tab)
    inner = tab.findChild(__import__("PyQt6.QtWidgets", fromlist=["QTabWidget"]).QTabWidget)
    labels = [inner.tabText(i) for i in range(inner.count())]
    assert "データ管理" in labels
```

- [ ] **Step 2: テストを実行して失敗を確認**

Run: `pytest tests/test_data_widget_hidden.py -v`
Expected: FAIL — 環境変数なしでも「データ管理」タブが常に存在する

- [ ] **Step 3: 環境変数でタブ表示を切り替え**

`app/ui/settings_tab.py:1-29`（import と `SettingsTab.__init__`）を以下に置き換える:

```python
# app/ui/settings_tab.py
import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QTabWidget, QFormLayout, QHBoxLayout,
    QLineEdit, QPushButton, QGroupBox, QTableWidget, QTableWidgetItem,
    QCheckBox, QMessageBox, QHeaderView, QLabel, QRadioButton, QButtonGroup,
    QFileDialog, QInputDialog, QTextEdit,
)
from app.utils.app_config import get_config, save_config, get_db_type, get_pg_config, get_html_export_path
from app.database.connection import get_session
from app.services.signature_service import (
    get_signatures, create_signature, update_signature,
    delete_signature, set_default
)
from app.services.staff_service import get_all_staff, create_staff, set_active


class SettingsTab(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        inner = QTabWidget()
        inner.addTab(_GraphSettingsWidget(), "Microsoft 365")
        inner.addTab(_SignatureWidget(), "署名管理")
        inner.addTab(_StaffWidget(), "職員管理")
        inner.addTab(_DbSettingsWidget(), "データベース接続")
        inner.addTab(_ExportSettingsWidget(), "出力設定")
        if os.environ.get("CCI_MAIL_DEV_TOOLS") == "1":
            inner.addTab(_DataWidget(), "データ管理")
        layout.addWidget(inner)
```

- [ ] **Step 4: テストを実行して成功を確認**

Run: `pytest tests/test_data_widget_hidden.py -v`
Expected: PASS

- [ ] **Step 5: コミット**

```bash
git add app/ui/settings_tab.py tests/test_data_widget_hidden.py
git commit -m "fix: 開発用一括削除タブを環境変数CCI_MAIL_DEV_TOOLS未設定時は非表示にする"
```

---

## Task 13: 名簿テーブルのメール列集約

**Files:**
- Modify: `app/ui/member_tab.py:82-113`（`_build` のテーブル定義）, `app/ui/member_tab.py:144-217`（`_load`）
- Test: `tests/test_member_tab_email_column.py`（新規）

**Interfaces:**
- Consumes: `member.email_addresses`（既存モデル、変更なし）

- [ ] **Step 1: 失敗するテストを書く**

```python
# tests/test_member_tab_email_column.py
def test_table_has_10_columns_with_single_email_column(qtbot, monkeypatch):
    monkeypatch.setattr("app.ui.member_tab.get_session", lambda: _FakeSession())
    monkeypatch.setattr("app.ui.member_tab.get_members", lambda *a, **k: [_Member()])

    from app.ui.member_tab import MemberTab
    tab = MemberTab()
    qtbot.addWidget(tab)

    headers = [tab._table.horizontalHeaderItem(i).text()
               for i in range(tab._table.columnCount())]
    assert tab._table.columnCount() == 10
    assert "メール(件数)" in headers
    email_col = headers.index("メール(件数)")
    assert tab._table.item(0, email_col).text() == "2件"


class _Email:
    def __init__(self, address, label=""):
        self.address = address
        self.label = label


class _Member:
    def __init__(self):
        self.id = 1
        self.member_number = "A-001"
        self.organization_name = "テスト商事"
        self.organization_kana = ""
        self.name = "山田太郎"
        self.name_kana = ""
        self.title = ""
        self.position = None
        self.email_addresses = [_Email("a@example.com"), _Email("b@example.com")]
        self.is_active = True
        self.updated_at = None
        self.photo_thumb = None


class _FakeSession:
    def close(self):
        pass
```

- [ ] **Step 2: テストを実行して失敗を確認**

Run: `pytest tests/test_member_tab_email_column.py -v`
Expected: FAIL — `assert 14 == 10`

- [ ] **Step 3: メール列を1列に集約**

`app/ui/member_tab.py:82-93`（テーブル列定義）を以下に置き換える:

```python
        # 一覧テーブル
        self._table = QTableWidget(0, 10)
        self._table.setHorizontalHeaderLabels([
            "写真",
            "会員番号", "会議所役職", "事業所名", "事業所名フリガナ",
            "氏名", "氏名フリガナ", "役職名",
            "メール(件数)", "最終更新日",
        ])
        self._table.horizontalHeader().setSectionResizeMode(
            3, QHeaderView.ResizeMode.Interactive)
        self._table.setColumnWidth(0, 44)
        self._table.setColumnWidth(3, 200)
```

`app/ui/member_tab.py:195-208`（メール列〜最終更新日の描画部分）を以下に置き換える。件数のみを表示し、宛先詳細（各アドレス・ラベル）は編集ダイアログ（`MemberEditDialog`）側で確認する運用とする:

```python
                # Col 8: メール件数（詳細は編集画面で確認）
                item = QTableWidgetItem(f"{len(m.email_addresses)}件")
                if is_retired:
                    item.setForeground(gray)
                self._table.setItem(row, 8, item)

                # Col 9: 最終更新日
                upd = m.updated_at.strftime("%Y/%m/%d") if m.updated_at else ""
                item = QTableWidgetItem(upd)
                if is_retired:
                    item.setForeground(gray)
                self._table.setItem(row, 9, item)
```

- [ ] **Step 4: テストを実行して成功を確認**

Run: `pytest tests/test_member_tab_email_column.py -v`
Expected: PASS

- [ ] **Step 5: コミット**

```bash
git add app/ui/member_tab.py tests/test_member_tab_email_column.py
git commit -m "refactor: 名簿テーブルのメール列を1列に集約し横スクロールを削減"
```

---

## Task 14: 名簿・送信履歴テーブルのソート機能

**Files:**
- Modify: `app/ui/member_tab.py:144-217`（`_load` 末尾）, `app/ui/history_tab.py:66-87`（`_load_jobs` 末尾）
- Test: `tests/test_table_sorting.py`（新規）

**Interfaces:**
- Consumes: なし（`QTableWidget.setSortingEnabled` は標準機能）

- [ ] **Step 1: 失敗するテストを書く**

```python
# tests/test_table_sorting.py
def test_member_table_sorting_enabled(qtbot, monkeypatch):
    monkeypatch.setattr("app.ui.member_tab.get_session", lambda: _FakeSession())
    monkeypatch.setattr("app.ui.member_tab.get_members", lambda *a, **k: [])

    from app.ui.member_tab import MemberTab
    tab = MemberTab()
    qtbot.addWidget(tab)
    assert tab._table.isSortingEnabled() is True


def test_history_job_table_sorting_enabled(qtbot, monkeypatch):
    monkeypatch.setattr("app.ui.history_tab.get_session", lambda: _FakeSession())
    monkeypatch.setattr("app.ui.history_tab.get_jobs", lambda s: [])

    from app.ui.history_tab import HistoryTab
    tab = HistoryTab()
    qtbot.addWidget(tab)
    assert tab._job_table.isSortingEnabled() is True


class _FakeSession:
    def close(self):
        pass
```

- [ ] **Step 2: テストを実行して失敗を確認**

Run: `pytest tests/test_table_sorting.py -v`
Expected: FAIL — `assert False is True`

- [ ] **Step 3: 行挿入完了後にソートを有効化**

`app/ui/member_tab.py:144-146`（`_load` 冒頭）でソートを一時停止し、末尾で再度有効化する。`_load` メソッド内、`self._table.setRowCount(0)` の直前に `self._table.setSortingEnabled(False)` を、`_on_selection_changed()`（Task 10実装済みの場合）の直前または `finally: session.close()` の直後に `self._table.setSortingEnabled(True)` を追加する:

```python
実装手順（`_load` メソッド本体のロジックは変更しない。挿入箇所のみのピンポイント編集）:

1. `app/ui/member_tab.py:147` の `session = get_session()` の直後に1行追加: `self._table.setSortingEnabled(False)`
2. `app/ui/member_tab.py:216-217` の `finally: session.close()` の直後（Task 10実装済みなら `self._on_selection_changed()` の直前）に1行追加: `self._table.setSortingEnabled(True)`

（`self._table.setRowCount(0)` や行描画の `for m in members:` ループなど、`try` ブロックの中身は一切変更しない。）

`app/ui/history_tab.py:66-87`（`_load_jobs`）についても同様にピンポイントで編集する:

1. `app/ui/history_tab.py:73` の `self._job_table.setRowCount(0)` の直前に1行追加: `self._job_table.setSortingEnabled(False)`
2. `app/ui/history_tab.py:85` の `for j in self._jobs:` ループが終わった直後・`self._log_table.setRowCount(0)`（86行目）の直前に1行追加: `self._job_table.setSortingEnabled(True)`

（ジョブ一覧の行描画ループ自体は変更しない。）
```

- [ ] **Step 4: テストを実行して成功を確認**

Run: `pytest tests/test_table_sorting.py -v`
Expected: PASS

- [ ] **Step 5: コミット**

```bash
git add app/ui/member_tab.py app/ui/history_tab.py tests/test_table_sorting.py
git commit -m "feat: 名簿・送信ジョブ一覧テーブルの列ヘッダークリックによるソートを有効化"
```

---

## Task 15: 空状態のガイダンス表示

**Files:**
- Modify: `app/ui/member_tab.py:24-114`（`_build`）, `app/ui/member_tab.py:144-217`（`_load`）, `app/ui/template_tab.py:28-96`（`_build`, `_load`）
- Test: `tests/test_empty_state_guidance.py`（新規）

**Interfaces:**
- Consumes: なし

- [ ] **Step 1: 失敗するテストを書く**

```python
# tests/test_empty_state_guidance.py
def test_member_tab_shows_guidance_when_empty(qtbot, monkeypatch):
    monkeypatch.setattr("app.ui.member_tab.get_session", lambda: _FakeSession())
    monkeypatch.setattr("app.ui.member_tab.get_members", lambda *a, **k: [])

    from app.ui.member_tab import MemberTab
    tab = MemberTab()
    qtbot.addWidget(tab)
    assert tab._empty_hint.isVisible() is True


def test_template_tab_shows_guidance_when_empty(qtbot, monkeypatch):
    monkeypatch.setattr("app.ui.template_tab.get_session", lambda: _FakeSession())
    monkeypatch.setattr("app.ui.template_tab.get_templates", lambda s: [])
    monkeypatch.setattr("app.ui.template_tab.get_signatures", lambda s: [])

    from app.ui.template_tab import TemplateTab
    tab = TemplateTab()
    qtbot.addWidget(tab)
    assert tab._empty_hint.isVisible() is True


class _FakeSession:
    def close(self):
        pass
```

- [ ] **Step 2: テストを実行して失敗を確認**

Run: `pytest tests/test_empty_state_guidance.py -v`
Expected: FAIL — `AttributeError: 'MemberTab' object has no attribute '_empty_hint'`

- [ ] **Step 3: 空状態ガイダンスラベルを追加**

`app/ui/member_tab.py:110-113`（テーブル追加直後）を以下に置き換える:

```python
        layout.addWidget(self._table)

        self._empty_hint = QLabel(
            "会員データがまだ登録されていません。「追加」ボタン、または"
            "「ファイル→インポート」から会員を登録してください。")
        self._empty_hint.setStyleSheet("color: #64748B; padding: 8px;")
        self._empty_hint.setVisible(False)
        layout.addWidget(self._empty_hint)

        self._count_label = QLabel("")
        layout.addWidget(self._count_label)
```

`app/ui/member_tab.py:209-216`（`_load` の件数表示部分の直後）に以下を追加:

```python
            active_count = sum(1 for m in members if m.is_active)
            if active_only:
                self._count_label.setText(f"{len(members)} 件")
            else:
                retired_count = len(members) - active_count
                self._count_label.setText(
                    f"{active_count} 件（議員退任者 {retired_count} 件を含む）")

            no_filter = (
                not self._search.text().strip()
                and self._pos_filter.currentData() is None
                and not self._show_inactive.isChecked()
            )
            self._empty_hint.setVisible(no_filter and len(members) == 0)
        finally:
            session.close()
```

`app/ui/template_tab.py:36-46`（左ペイン構築部分）の `left_layout.addLayout(btn_row)` の直後に追加:

```python
        left_layout.addWidget(QLabel("テンプレート一覧"))
        left_layout.addWidget(self._list)
        left_layout.addLayout(btn_row)
        self._empty_hint = QLabel(
            "テンプレートがまだありません。「新規」ボタンから作成してください。")
        self._empty_hint.setWordWrap(True)
        self._empty_hint.setStyleSheet("color: #64748B; padding: 4px;")
        self._empty_hint.setVisible(False)
        left_layout.addWidget(self._empty_hint)
        splitter.addWidget(left)
```

`app/ui/template_tab.py:90-104`（`_load`）末尾に追加:

```python
        self._sig_combo.blockSignals(True)
        self._sig_combo.clear()
        self._sig_combo.addItem("（なし）", None)
        for s in self._signatures:
            self._sig_combo.addItem(s.name, s.id)
        self._sig_combo.blockSignals(False)

        self._empty_hint.setVisible(len(self._templates) == 0)
```

- [ ] **Step 4: テストを実行して成功を確認**

Run: `pytest tests/test_empty_state_guidance.py -v`
Expected: PASS

- [ ] **Step 5: コミット**

```bash
git add app/ui/member_tab.py app/ui/template_tab.py tests/test_empty_state_guidance.py
git commit -m "feat: 名簿・テンプレートが0件のときに登録方法のガイダンスを表示"
```

---

## Task 16: キーボードショートカット（Ctrl+S / Ctrl+F）

**Files:**
- Modify: `app/ui/template_tab.py:28-30`（`_build` 冒頭）, `app/ui/member_tab.py:24-30`（`_build` 冒頭）
- Test: `tests/test_keyboard_shortcuts.py`（新規）

**Interfaces:**
- Consumes: `QShortcut`, `QKeySequence`（PyQt6標準）

- [ ] **Step 1: 失敗するテストを書く**

```python
# tests/test_keyboard_shortcuts.py
from PyQt6.QtGui import QKeySequence


def test_template_tab_ctrl_s_triggers_save(qtbot, monkeypatch):
    monkeypatch.setattr("app.ui.template_tab.get_session", lambda: _FakeSession())
    monkeypatch.setattr("app.ui.template_tab.get_templates", lambda s: [])
    monkeypatch.setattr("app.ui.template_tab.get_signatures", lambda s: [])

    from app.ui.template_tab import TemplateTab
    tab = TemplateTab()
    qtbot.addWidget(tab)

    called = []
    tab._save = lambda: called.append(True)
    shortcuts = [sc for sc in tab.findChildren(__import__(
        "PyQt6.QtGui", fromlist=["QShortcut"]).QShortcut)
        if sc.key() == QKeySequence("Ctrl+S")]
    assert shortcuts, "Ctrl+S ショートカットが登録されていない"


def test_member_tab_ctrl_f_focuses_search(qtbot, monkeypatch):
    monkeypatch.setattr("app.ui.member_tab.get_session", lambda: _FakeSession())
    monkeypatch.setattr("app.ui.member_tab.get_members", lambda *a, **k: [])

    from app.ui.member_tab import MemberTab
    tab = MemberTab()
    qtbot.addWidget(tab)
    shortcuts = [sc for sc in tab.findChildren(__import__(
        "PyQt6.QtGui", fromlist=["QShortcut"]).QShortcut)
        if sc.key() == QKeySequence("Ctrl+F")]
    assert shortcuts, "Ctrl+F ショートカットが登録されていない"


class _FakeSession:
    def close(self):
        pass
```

- [ ] **Step 2: テストを実行して失敗を確認**

Run: `pytest tests/test_keyboard_shortcuts.py -v`
Expected: FAIL — `assert shortcuts` が空リストで失敗

- [ ] **Step 3: ショートカットを登録**

`app/ui/template_tab.py:1-8` のimportに `QShortcut`（`PyQt6.QtGui`）を追加:

```python
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QListWidget, QListWidgetItem, QPushButton,
    QFormLayout, QLineEdit, QTextEdit, QComboBox,
    QLabel, QGroupBox, QMessageBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeySequence, QShortcut
```

`app/ui/template_tab.py:28-30`（`_build` 冒頭）に追加:

```python
    def _build(self):
        layout = QVBoxLayout(self)
        QShortcut(QKeySequence("Ctrl+S"), self).activated.connect(self._save)
        splitter = QSplitter(Qt.Orientation.Horizontal)
```

`app/ui/member_tab.py:7-8` の既存import行を以下に置き換える（`QKeySequence` / `QShortcut` を追加）:

```python
from PyQt6.QtCore import Qt, QPoint
from PyQt6.QtGui import QColor, QKeySequence, QShortcut
```

`app/ui/member_tab.py:24-27`（`_build` 冒頭）に追加:

```python
    def _build(self):
        layout = QVBoxLayout(self)
        QShortcut(QKeySequence("Ctrl+F"), self).activated.connect(
            lambda: (self._search.setFocus(), self._search.selectAll()))
```

- [ ] **Step 4: テストを実行して成功を確認**

Run: `pytest tests/test_keyboard_shortcuts.py -v`
Expected: PASS

- [ ] **Step 5: コミット**

```bash
git add app/ui/template_tab.py app/ui/member_tab.py tests/test_keyboard_shortcuts.py
git commit -m "feat: テンプレート編集にCtrl+S保存、名簿検索にCtrl+Fフォーカスのショートカットを追加"
```

---

## Task 17: ログインダイアログ改善（未選択時ボタン無効化＋前回担当者記憶）

**Files:**
- Modify: `app/ui/dialogs/login_dialog.py:8-125`, `app/services/settings_service.py`
- Test: `tests/test_login_dialog.py`（新規）

**Interfaces:**
- Produces: `settings_service.get_last_staff() -> str`, `settings_service.set_last_staff(name: str) -> None`

- [ ] **Step 1: 失敗するテストを書く**

```python
# tests/test_login_dialog.py
def test_login_button_disabled_until_staff_selected(qtbot, monkeypatch, tmp_path):
    monkeypatch.setattr(
        "app.services.settings_service._PATH", tmp_path / "ui_settings.json")

    class _Staff:
        def __init__(self, name):
            self.name = name
            self.is_active = True

    monkeypatch.setattr(
        "app.ui.dialogs.login_dialog.get_session", lambda: _FakeSession())
    monkeypatch.setattr(
        "app.ui.dialogs.login_dialog.get_all_staff",
        lambda s: [_Staff("担当者A"), _Staff("担当者B")])

    from app.ui.dialogs.login_dialog import LoginDialog
    dlg = LoginDialog()
    qtbot.addWidget(dlg)

    assert dlg._btn_login.isEnabled() is False
    dlg._combo.setCurrentIndex(1)
    assert dlg._btn_login.isEnabled() is True


def test_last_staff_is_remembered(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.services.settings_service._PATH", tmp_path / "ui_settings.json")
    from app.services.settings_service import get_last_staff, set_last_staff
    assert get_last_staff() == ""
    set_last_staff("担当者A")
    assert get_last_staff() == "担当者A"


class _FakeSession:
    def close(self):
        pass
```

- [ ] **Step 2: テストを実行して失敗を確認**

Run: `pytest tests/test_login_dialog.py -v`
Expected: FAIL — `ImportError: cannot import name 'get_last_staff'`

- [ ] **Step 3: `settings_service` に前回担当者の記憶を追加し、ログインダイアログを改修**

`app/services/settings_service.py` の末尾に追加:

```python
def get_last_staff() -> str:
    return _load().get("last_staff", "")


def set_last_staff(name: str):
    data = _load()
    data["last_staff"] = name
    _save(data)
```

`app/ui/dialogs/login_dialog.py:1-9` のimportを以下に置き換える:

```python
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QPushButton, QMessageBox, QInputDialog, QFrame
)
from PyQt6.QtCore import Qt
from app.database.connection import get_session
from app.services.staff_service import get_all_staff, create_staff
from app.services.settings_service import get_last_staff, set_last_staff
```

`app/ui/dialogs/login_dialog.py:32-41`（ログインボタン部分）を以下に置き換える:

```python
        btn_row = QHBoxLayout()
        self._btn_add = QPushButton("職員を追加")
        self._btn_add.clicked.connect(self._add_staff)
        self._btn_login = QPushButton("ログイン")
        self._btn_login.setDefault(True)
        self._btn_login.setEnabled(False)
        self._btn_login.clicked.connect(self._login)
        self._combo.currentIndexChanged.connect(
            lambda: self._btn_login.setEnabled(bool(self._combo.currentData())))
        btn_row.addWidget(self._btn_add)
        btn_row.addStretch()
        btn_row.addWidget(self._btn_login)
        layout.addLayout(btn_row)
```

`app/ui/dialogs/login_dialog.py:75-90`（`_load_staff`）を以下に置き換える:

```python
    def _load_staff(self):
        session = get_session()
        try:
            staff = [s for s in get_all_staff(session) if s.is_active]
        finally:
            session.close()
        self._combo.clear()
        self._combo.addItem("（選択してください）", "")
        last_staff = get_last_staff()
        last_index = 0
        for s in staff:
            self._combo.addItem(s.name, s.name)
            if s.name == last_staff:
                last_index = self._combo.count() - 1
        self._combo.setCurrentIndex(last_index)

        no_staff = len(staff) == 0
        self._hint.setVisible(no_staff)
        self._btn_add.setVisible(no_staff)
        self._btn_login.setEnabled(bool(self._combo.currentData()))
```

`app/ui/dialogs/login_dialog.py:106-113`（`_login`）を以下に置き換える:

```python
    def _login(self):
        name = self._combo.currentData()
        if not name:
            QMessageBox.warning(self, "未選択", "担当者を選択してください。")
            return
        self._staff_name = name
        self._readonly = False
        set_last_staff(name)
        self.accept()
```

（`self._combo` に紐づく古い `btn_login` ローカル変数参照は `self._btn_login` に統一済み。）

- [ ] **Step 4: テストを実行して成功を確認**

Run: `pytest tests/test_login_dialog.py -v`
Expected: PASS

- [ ] **Step 5: コミット**

```bash
git add app/services/settings_service.py app/ui/dialogs/login_dialog.py tests/test_login_dialog.py
git commit -m "feat: ログインダイアログで担当者未選択時はログインボタンを無効化し前回の担当者を記憶する"
```

---

## 対象外事項

- **初期ウィンドウサイズの拡大**（評価書「低優先度」の最終項目）: `C:\Users\taka\.claude\CLAUDE.md` により「ウィンドウ初期サイズ: 幅780px×高さ728px以内」が全プロジェクト共通ルールとして定められており、評価書の提案（初回起動時に最大化気味のサイズにする）と直接矛盾する。既存の `MainWindow.resize(780, 728)`（`app/ui/main_window.py:24`）は変更しない。送信タブの窮屈さは Task 11（本文欄拡大表示ボタン）で部分的に緩和する。

---

## Self-Review メモ

- 評価書の16項目すべてに対応するタスク（Task 1〜17、Task間で1項目が2タスクに分かれるため計17タスク）を用意した。ウィンドウサイズ拡大のみCLAUDE.mdのルールと矛盾するため対象外とし、理由を明記した。
- 各タスクは既存の対象ファイル・行番号を明示し、プレースホルダーなしで完全なコードを記載した。
- Task 3で導入した `_take_snapshot` / `_is_dirty` パターンをTask 4・Task 8で再利用する形にし、命名の一貫性を確認した。
- Task 13のテスト期待値（`"2件"`）と実装例（代表アドレス＋残数表示）の不一致に気づき、実装コメント内で「件数のみ表示に統一する場合はテストをそのまま使う」旨を明記して矛盾を解消した。
