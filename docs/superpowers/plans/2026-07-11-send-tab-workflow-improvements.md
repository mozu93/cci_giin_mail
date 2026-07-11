# 送信タブ ワークフロー改善 実装計画

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `docs/superpowers/specs/2026-07-11-send-tab-workflow-improvements-design.md` に基づき、送信タブ（`app/ui/send_tab.py`）の宛先選択・テンプレート運用・添付ファイル運用・テスト送信を改善する。

**Architecture:** 既存の `send_tab.py` / `template_tab.py` / `attach_confirm_dialog.py` に対する局所的な修正の積み重ね。サービス層・DBスキーマの変更なし。新規ファイルの作成もなし。

**Tech Stack:** Python 3.11+, PyQt6, SQLAlchemy, pytest, pytest-qt

## Global Constraints

- ウィンドウ初期サイズは 780×728px 以内に収めること（`C:\Users\taka\.claude\CLAUDE.md` の全プロジェクト共通ルール）。本計画はStep3の非表示化・Step4の折りたたみにより、むしろ縦方向のスペースを削減する方向であり、このルールに抵触しない。
- 既存の命名規則・実装パターン（`get_session()` の都度生成、`QMessageBox` の既定ボタンNo、`inline_status.show_inline_message` によるインライン通知、`os.environ.get("CCI_MAIL_DEV_TOOLS") == "1"` による開発者フラグ）を踏襲する。
- サービス層・DBスキーマ・既存の公開関数シグネチャは変更しない（UI層のみの変更に限定）。
- 各タスクは独立してテスト・コミット可能。Task 2→3、Task 4→6→7 の間には依存関係があるため、Task番号順に実施する。
- テストは pytest-qt の `qtbot` フィクスチャを使う。実DB（`get_session()`）へのアクセスが発生する箇所は `monkeypatch` でサービス関数を差し替え、テストがローカルの `app_config.json` / 実DBに依存しないようにする。ウィジェットの表示状態（`isVisible()`）を検証するテストは、必ず `qtbot.addWidget(tab)` の後に `tab.show()` を呼ぶ（`tests/test_empty_state_guidance.py` の既存パターンを踏襲）。

---

## タスク一覧

| # | 内容 | 対象ファイル |
|---|---|---|
| 1 | Step1に「名簿から選択」モードを追加しデフォルト化 | send_tab.py |
| 2 | Step2にプレースホルダー挿入ボタンを追加 | send_tab.py |
| 3 | Step2に「テンプレートとして保存」ボタンを追加 | send_tab.py |
| 4 | ステップ番号の動的採番とStep3（差し込みデータ）の開発者フラグ化 | send_tab.py |
| 5 | テンプレートタブのプレースホルダーを開発者フラグで統一 | template_tab.py |
| 6 | Step4（添付ファイル）を使用時のみ展開表示に | send_tab.py |
| 7 | 個別添付ファイルのワイルドカードマッチングと複数ファイル対応 | send_tab.py, attach_confirm_dialog.py |
| 8 | テスト送信ボタンにテスト送信先アドレスを表示 | send_tab.py |

---

## Task 1: Step1に「名簿から選択」モードを追加しデフォルト化

**Files:**
- Modify: `app/ui/send_tab.py`（`_build_step1` の `mode_row` 部分、`_clear_all` のモードリセット行）
- Test: `tests/test_send_tab_list_mode.py`（新規）

**Interfaces:**
- Produces: `SendTab._rb_by_list`（`QRadioButton`）

- [ ] **Step 1: 失敗するテストを書く**

```python
# tests/test_send_tab_list_mode.py
class _FakeSession:
    def close(self):
        pass


def _patch_common(monkeypatch):
    monkeypatch.setattr("app.ui.send_tab.get_session", lambda: _FakeSession())
    monkeypatch.setattr("app.ui.send_tab.get_positions", lambda s: [])
    monkeypatch.setattr("app.ui.send_tab.get_committees", lambda s: [])
    monkeypatch.setattr("app.ui.send_tab.get_members", lambda s: [])
    monkeypatch.setattr("app.ui.send_tab.get_templates", lambda s: [])
    monkeypatch.setattr("app.ui.send_tab.get_signatures", lambda s: [])
    monkeypatch.setattr("app.ui.send_tab.get_default_signature", lambda s: None)


def test_list_mode_is_default_and_hides_filter_panels(qtbot, monkeypatch):
    _patch_common(monkeypatch)
    from app.ui.send_tab import SendTab
    tab = SendTab(staff_name="担当者A")
    qtbot.addWidget(tab)
    tab.show()

    assert tab._rb_by_list.isChecked() is True
    assert tab._pos_panel.isVisible() is False
    assert tab._committee_panel.isVisible() is False
    assert tab._attend_panel.isVisible() is False


def test_switching_to_pos_mode_shows_pos_panel_then_back_to_list_hides_it(qtbot, monkeypatch):
    _patch_common(monkeypatch)
    from app.ui.send_tab import SendTab
    tab = SendTab(staff_name="担当者A")
    qtbot.addWidget(tab)
    tab.show()

    tab._rb_by_pos.setChecked(True)
    assert tab._pos_panel.isVisible() is True

    tab._rb_by_list.setChecked(True)
    assert tab._pos_panel.isVisible() is False


def test_switching_from_attend_directly_to_list_hides_attend_panel(qtbot, monkeypatch):
    _patch_common(monkeypatch)
    from app.ui.send_tab import SendTab
    tab = SendTab(staff_name="担当者A")
    qtbot.addWidget(tab)
    tab.show()

    tab._rb_by_attend.setChecked(True)
    assert tab._attend_panel.isVisible() is True

    tab._rb_by_list.setChecked(True)
    assert tab._attend_panel.isVisible() is False


def test_clear_all_resets_to_list_mode(qtbot, monkeypatch):
    _patch_common(monkeypatch)
    from app.ui.send_tab import SendTab
    tab = SendTab(staff_name="担当者A")
    qtbot.addWidget(tab)

    tab._rb_by_pos.setChecked(True)
    tab._clear_all()
    assert tab._rb_by_list.isChecked() is True
```

- [ ] **Step 2: テストを実行して失敗を確認**

Run: `pytest tests/test_send_tab_list_mode.py -v`
Expected: FAIL — `AttributeError: 'SendTab' object has no attribute '_rb_by_list'`

- [ ] **Step 3: `_build_step1` の `mode_row` と `_clear_all` を変更**

`_build_step1` メソッド内、`mode_row = QHBoxLayout()` から `layout.addLayout(mode_row)` までのブロックを以下に置き換える:

```python
        mode_row = QHBoxLayout()
        self._rb_by_list = QRadioButton("名簿から選択")
        self._rb_by_pos = QRadioButton("役職で選ぶ")
        self._rb_by_committee = QRadioButton("委員会で選ぶ")
        self._rb_by_attend = QRadioButton("会議の出欠で選ぶ")
        self._rb_by_list.setChecked(True)
        bg = QButtonGroup(self)
        bg.addButton(self._rb_by_list)
        bg.addButton(self._rb_by_pos)
        bg.addButton(self._rb_by_committee)
        bg.addButton(self._rb_by_attend)
        self._rb_by_list.toggled.connect(self._on_mode_change)
        self._rb_by_pos.toggled.connect(self._on_mode_change)
        self._rb_by_committee.toggled.connect(self._on_mode_change)
        self._rb_by_attend.toggled.connect(self._on_mode_change)
        mode_row.addWidget(self._rb_by_list)
        mode_row.addWidget(self._rb_by_pos)
        mode_row.addWidget(self._rb_by_committee)
        mode_row.addWidget(self._rb_by_attend)
        mode_row.addStretch()
        layout.addLayout(mode_row)
```

`_clear_all` メソッドの先頭行 `self._rb_by_pos.setChecked(True)` を以下に置き換える:

```python
        self._rb_by_list.setChecked(True)
```

- [ ] **Step 4: テストを実行して成功を確認**

Run: `pytest tests/test_send_tab_list_mode.py -v`
Expected: PASS

- [ ] **Step 5: コミット**

```bash
git add app/ui/send_tab.py tests/test_send_tab_list_mode.py
git commit -m "feat: 送信タブStep1に名簿から選択モードを追加しデフォルト化"
```

---

## Task 2: Step2にプレースホルダー挿入ボタンを追加

**Files:**
- Modify: `app/ui/send_tab.py`（モジュール定数、`_build_step2`、新規メソッド `_insert_placeholder`）
- Test: `tests/test_send_tab_placeholder.py`（新規）

**Interfaces:**
- Produces: `SendTab._insert_placeholder(placeholder: str) -> None`、モジュール関数 `_dev_tools_enabled() -> bool`、モジュール定数 `_BASE_PLACEHOLDERS`, `_MERGE_PLACEHOLDERS`

- [ ] **Step 1: 失敗するテストを書く**

```python
# tests/test_send_tab_placeholder.py
from PyQt6.QtWidgets import QPushButton


class _FakeSession:
    def close(self):
        pass


def _patch_common(monkeypatch):
    monkeypatch.setattr("app.ui.send_tab.get_session", lambda: _FakeSession())
    monkeypatch.setattr("app.ui.send_tab.get_positions", lambda s: [])
    monkeypatch.setattr("app.ui.send_tab.get_committees", lambda s: [])
    monkeypatch.setattr("app.ui.send_tab.get_members", lambda s: [])
    monkeypatch.setattr("app.ui.send_tab.get_templates", lambda s: [])
    monkeypatch.setattr("app.ui.send_tab.get_signatures", lambda s: [])
    monkeypatch.setattr("app.ui.send_tab.get_default_signature", lambda s: None)


def _placeholder_labels(tab):
    return [b.text() for b in tab.findChildren(QPushButton) if b.text().startswith("{")]


def test_placeholder_click_inserts_text_into_body(qtbot, monkeypatch):
    _patch_common(monkeypatch)
    from app.ui.send_tab import SendTab
    tab = SendTab(staff_name="担当者A")
    qtbot.addWidget(tab)

    tab._body_edit.clear()
    tab._insert_placeholder("{事業所名}")
    assert tab._body_edit.toPlainText() == "{事業所名}"


def test_merge_placeholders_hidden_without_dev_flag(qtbot, monkeypatch):
    monkeypatch.delenv("CCI_MAIL_DEV_TOOLS", raising=False)
    _patch_common(monkeypatch)
    from app.ui.send_tab import SendTab
    tab = SendTab(staff_name="担当者A")
    qtbot.addWidget(tab)

    labels = _placeholder_labels(tab)
    assert "{col1}" not in labels
    assert "{事業所名}" in labels


def test_merge_placeholders_shown_with_dev_flag(qtbot, monkeypatch):
    monkeypatch.setenv("CCI_MAIL_DEV_TOOLS", "1")
    _patch_common(monkeypatch)
    from app.ui.send_tab import SendTab
    tab = SendTab(staff_name="担当者A")
    qtbot.addWidget(tab)

    labels = _placeholder_labels(tab)
    assert "{col1}" in labels
```

- [ ] **Step 2: テストを実行して失敗を確認**

Run: `pytest tests/test_send_tab_placeholder.py -v`
Expected: FAIL — `AttributeError: 'SendTab' object has no attribute '_insert_placeholder'`

- [ ] **Step 3: モジュール定数と `_build_step2`、`_insert_placeholder` を実装**

`app/ui/send_tab.py` の import群の直後（`class _SendWorker` 定義の前）に以下を追加する:

```python
_BASE_PLACEHOLDERS = ["{事業所名}", "{役職名}", "{氏名}", "{会議所役職名}"]
_MERGE_PLACEHOLDERS = ["{col1}", "{col2}", "{col3}", "{col4}", "{col5}"]


def _dev_tools_enabled() -> bool:
    return os.environ.get("CCI_MAIL_DEV_TOOLS") == "1"
```

`_build_step2` メソッド全体を以下に置き換える:

```python
    def _build_step2(self) -> QGroupBox:
        grp = QGroupBox("Step 2：テンプレート・署名選択")
        outer = QVBoxLayout(grp)

        f = QFormLayout()
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
        outer.addLayout(f)

        ph_row = QHBoxLayout()
        placeholders = list(_BASE_PLACEHOLDERS)
        if _dev_tools_enabled():
            placeholders += _MERGE_PLACEHOLDERS
        for ph in placeholders:
            btn = QPushButton(ph)
            btn.setFlat(True)
            btn.setStyleSheet(
                "font-size: 12px; color: #1E40AF; padding: 2px 6px;"
                "border: 1px solid #BFDBFE; border-radius: 3px;")
            btn.clicked.connect(lambda checked, p=ph: self._insert_placeholder(p))
            ph_row.addWidget(btn)
        ph_row.addStretch()
        outer.addLayout(ph_row)

        return grp
```

`_insert_placeholder` メソッドを `_expand_body_edit` メソッドの直後に追加する:

```python
    def _insert_placeholder(self, placeholder: str):
        self._body_edit.setFocus()
        self._body_edit.insertPlainText(placeholder)
```

- [ ] **Step 4: テストを実行して成功を確認**

Run: `pytest tests/test_send_tab_placeholder.py -v`
Expected: PASS

- [ ] **Step 5: コミット**

```bash
git add app/ui/send_tab.py tests/test_send_tab_placeholder.py
git commit -m "feat: 送信タブStep2にプレースホルダー挿入ボタンを追加"
```

---

## Task 3: Step2に「テンプレートとして保存」ボタンを追加

**Files:**
- Modify: `app/ui/send_tab.py`（import、`_build_step2`、新規メソッド `_save_as_template`）
- Test: `tests/test_send_tab_save_template.py`（新規）

**Interfaces:**
- Consumes: `create_template(session, name, subject, body, signature_id=None)`, `update_template(session, template_id, **kwargs)`（`template_service.py`、変更なし）
- Produces: `SendTab._save_as_template() -> None`, `SendTab._step2_status_label`（`QLabel`）

- [ ] **Step 1: 失敗するテストを書く**

```python
# tests/test_send_tab_save_template.py
from PyQt6.QtWidgets import QInputDialog, QMessageBox


class _FakeSession:
    def close(self):
        pass


class _Template:
    def __init__(self, id, name, subject="", body="", signature_id=None):
        self.id = id
        self.name = name
        self.subject = subject
        self.body = body
        self.signature_id = signature_id


def _patch_common(monkeypatch, templates=None):
    monkeypatch.setattr("app.ui.send_tab.get_session", lambda: _FakeSession())
    monkeypatch.setattr("app.ui.send_tab.get_positions", lambda s: [])
    monkeypatch.setattr("app.ui.send_tab.get_committees", lambda s: [])
    monkeypatch.setattr("app.ui.send_tab.get_members", lambda s: [])
    monkeypatch.setattr("app.ui.send_tab.get_templates", lambda s: templates or [])
    monkeypatch.setattr("app.ui.send_tab.get_signatures", lambda s: [])
    monkeypatch.setattr("app.ui.send_tab.get_default_signature", lambda s: None)


def test_save_as_template_creates_new_when_none_selected(qtbot, monkeypatch):
    _patch_common(monkeypatch)
    created = {}

    def fake_create_template(session, name, subject, body, signature_id=None):
        created["args"] = (name, subject, body, signature_id)
        return _Template(99, name, subject, body, signature_id)

    monkeypatch.setattr("app.ui.send_tab.create_template", fake_create_template)
    monkeypatch.setattr(QInputDialog, "getText",
                        staticmethod(lambda *a, **k: ("新テンプレ", True)))

    from app.ui.send_tab import SendTab
    tab = SendTab(staff_name="担当者A")
    qtbot.addWidget(tab)
    tab._subject_edit.setText("件名A")
    tab._body_edit.setPlainText("本文A")

    tab._save_as_template()

    assert created["args"] == ("新テンプレ", "件名A", "本文A", None)


def test_save_as_template_overwrites_when_selected(qtbot, monkeypatch):
    tmpl = _Template(5, "既存テンプレ", "旧件名", "旧本文")
    _patch_common(monkeypatch, templates=[tmpl])
    updated = {}

    def fake_update_template(session, template_id, **kwargs):
        updated["args"] = (template_id, kwargs)
        return tmpl

    monkeypatch.setattr("app.ui.send_tab.update_template", fake_update_template)
    monkeypatch.setattr(QMessageBox, "question",
                        staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes))

    from app.ui.send_tab import SendTab
    tab = SendTab(staff_name="担当者A")
    qtbot.addWidget(tab)
    for i in range(tab._template_combo.count()):
        if tab._template_combo.itemData(i) == 5:
            tab._template_combo.setCurrentIndex(i)
            break
    tab._subject_edit.setText("新件名")
    tab._body_edit.setPlainText("新本文")

    tab._save_as_template()

    assert updated["args"][0] == 5
    assert updated["args"][1]["subject"] == "新件名"
    assert updated["args"][1]["body"] == "新本文"


def test_save_as_template_requires_subject_and_body(qtbot, monkeypatch):
    _patch_common(monkeypatch)

    from app.ui.send_tab import SendTab
    tab = SendTab(staff_name="担当者A")
    qtbot.addWidget(tab)
    tab._subject_edit.clear()
    tab._body_edit.clear()

    warned = []
    monkeypatch.setattr(QMessageBox, "warning",
                        staticmethod(lambda *a, **k: warned.append(True)))

    tab._save_as_template()
    assert warned, "件名・本文が空の場合は警告を表示すること"
```

- [ ] **Step 2: テストを実行して失敗を確認**

Run: `pytest tests/test_send_tab_save_template.py -v`
Expected: FAIL — `AttributeError: 'SendTab' object has no attribute '_save_as_template'`

- [ ] **Step 3: import追加と`_build_step2`拡張、`_save_as_template`実装**

`app/ui/send_tab.py` 冒頭のimportを以下に置き換える:

```python
import os
import glob
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QScrollArea,
    QGroupBox, QFormLayout, QComboBox, QLabel,
    QPushButton, QCheckBox, QLineEdit, QTextEdit,
    QProgressBar, QFileDialog, QMessageBox, QInputDialog,
    QListWidget, QListWidgetItem, QRadioButton, QButtonGroup,
    QSplitter,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from app.database.connection import get_session
from app.services.member_service import get_members
from app.services.template_service import (
    get_templates, get_template, create_template, update_template
)
from app.services.signature_service import get_signatures, get_default_signature
from app.services.position_service import get_positions
from app.services.committee_service import get_committees
from app.services.staff_service import get_staff_by_name
from app.services.email_service import compile_send_targets, send_mail, send_test_mail
from app.services.send_job_service import create_job, start_job, finish_job, add_log
from app.utils.app_config import get_graph_config
from app.ui.recipient_panel import RecipientPanel
```

（`import glob` はTask 7で使用するが、import整理の手間を減らすためここで先に追加しておく。）

`_build_step2` メソッドの `return grp` の直前に以下を追加する（Task 2で追加したプレースホルダー行の直後）:

```python
        btn_row2 = QHBoxLayout()
        self._btn_save_template = QPushButton("テンプレートとして保存")
        self._btn_save_template.clicked.connect(self._save_as_template)
        btn_row2.addWidget(self._btn_save_template)
        btn_row2.addStretch()
        outer.addLayout(btn_row2)
        self._step2_status_label = QLabel("")
        outer.addWidget(self._step2_status_label)
```

`_insert_placeholder`メソッドの直後に`_save_as_template`メソッドを追加する:

```python
    def _save_as_template(self):
        subject = self._subject_edit.text().strip()
        body = self._body_edit.toPlainText().strip()
        if not subject or not body:
            QMessageBox.warning(self, "入力エラー", "件名と本文を入力してください。")
            return
        sig_id = self._sig_combo.currentData()
        tmpl_id = self._template_combo.currentData()
        session = get_session()
        try:
            if tmpl_id:
                tmpl_name = self._template_combo.currentText()
                ret = QMessageBox.question(
                    self, "上書き確認",
                    f"テンプレート「{tmpl_name}」を上書き保存しますか？",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No)
                if ret != QMessageBox.StandardButton.Yes:
                    return
                update_template(session, tmpl_id, subject=subject, body=body,
                                signature_id=sig_id)
                saved_id = tmpl_id
            else:
                name, ok = QInputDialog.getText(
                    self, "テンプレート名", "新しいテンプレート名を入力してください：")
                name = name.strip()
                if not ok or not name:
                    return
                new_tmpl = create_template(session, name, subject, body,
                                           signature_id=sig_id)
                saved_id = new_tmpl.id
        finally:
            session.close()

        self._load_combos()
        for i in range(self._template_combo.count()):
            if self._template_combo.itemData(i) == saved_id:
                self._template_combo.setCurrentIndex(i)
                break
        from app.ui.widgets.inline_status import show_inline_message
        show_inline_message(self._step2_status_label, "テンプレートを保存しました")
```

- [ ] **Step 4: テストを実行して成功を確認**

Run: `pytest tests/test_send_tab_save_template.py -v`
Expected: PASS

- [ ] **Step 5: コミット**

```bash
git add app/ui/send_tab.py tests/test_send_tab_save_template.py
git commit -m "feat: 送信タブStep2にテンプレートとして保存するボタンを追加"
```

---

## Task 4: ステップ番号の動的採番とStep3（差し込みデータ）の開発者フラグ化

**Files:**
- Modify: `app/ui/send_tab.py`（`_build_left_column`、`_build_step1`/`_build_step2`のタイトル、`_build_step3`→`_build_merge_section`、`_build_step4`→`_build_attach_section`、`_build_step5`→`_build_final_section`のリネームとタイトル変更、`_clear_all`の`_merge_status`ガード）
- Test: `tests/test_send_tab_step_numbering.py`（新規）

**Interfaces:**
- Consumes: `_dev_tools_enabled()`（Task 2で追加）
- Produces: `SendTab._build_merge_section() -> QGroupBox`, `SendTab._build_attach_section() -> QGroupBox`, `SendTab._build_final_section() -> QGroupBox`（それぞれ旧`_build_step3`/`_build_step4`/`_build_step5`のリネーム）

- [ ] **Step 1: 失敗するテストを書く**

```python
# tests/test_send_tab_step_numbering.py
from PyQt6.QtWidgets import QGroupBox


class _FakeSession:
    def close(self):
        pass


def _patch_common(monkeypatch):
    monkeypatch.setattr("app.ui.send_tab.get_session", lambda: _FakeSession())
    monkeypatch.setattr("app.ui.send_tab.get_positions", lambda s: [])
    monkeypatch.setattr("app.ui.send_tab.get_committees", lambda s: [])
    monkeypatch.setattr("app.ui.send_tab.get_members", lambda s: [])
    monkeypatch.setattr("app.ui.send_tab.get_templates", lambda s: [])
    monkeypatch.setattr("app.ui.send_tab.get_signatures", lambda s: [])
    monkeypatch.setattr("app.ui.send_tab.get_default_signature", lambda s: None)


def test_step_titles_without_dev_flag(qtbot, monkeypatch):
    monkeypatch.delenv("CCI_MAIL_DEV_TOOLS", raising=False)
    _patch_common(monkeypatch)
    from app.ui.send_tab import SendTab
    tab = SendTab(staff_name="担当者A")
    qtbot.addWidget(tab)

    assert not hasattr(tab, "_merge_status")
    titles = [grp.title() for grp in tab.findChildren(QGroupBox)]
    assert "Step 1：宛先条件" in titles
    assert "Step 2：テンプレート・署名選択" in titles
    assert "Step 3：添付ファイル（任意）" in titles
    assert "Step 4：最終確認・送信" in titles
    assert not any("差し込みデータ" in t for t in titles)


def test_step_titles_with_dev_flag(qtbot, monkeypatch):
    monkeypatch.setenv("CCI_MAIL_DEV_TOOLS", "1")
    _patch_common(monkeypatch)
    from app.ui.send_tab import SendTab
    tab = SendTab(staff_name="担当者A")
    qtbot.addWidget(tab)

    assert hasattr(tab, "_merge_status")
    titles = [grp.title() for grp in tab.findChildren(QGroupBox)]
    assert "Step 3：差し込みデータ（任意）" in titles
    assert "Step 4：添付ファイル（任意）" in titles
    assert "Step 5：最終確認・送信" in titles


def test_clear_all_does_not_crash_without_merge_section(qtbot, monkeypatch):
    monkeypatch.delenv("CCI_MAIL_DEV_TOOLS", raising=False)
    _patch_common(monkeypatch)
    from app.ui.send_tab import SendTab
    tab = SendTab(staff_name="担当者A")
    qtbot.addWidget(tab)
    tab._clear_all()  # 例外が発生しないこと
```

- [ ] **Step 2: テストを実行して失敗を確認**

Run: `pytest tests/test_send_tab_step_numbering.py -v`
Expected: FAIL — `assert "Step 3：添付ファイル（任意）" in titles`（現状は`_build_step3`が差し込みデータのため）

- [ ] **Step 3: `_build_left_column`の再構成とメソッドのリネーム**

`_build_left_column`メソッドを以下に置き換える:

```python
    def _build_left_column(self) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)

        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setSpacing(8)
        layout.setContentsMargins(4, 4, 4, 4)

        btn_clear = QPushButton("すべてクリア")
        btn_clear.clicked.connect(self._clear_all)
        layout.addWidget(btn_clear)

        sections = [self._build_step1(), self._build_step2()]
        if _dev_tools_enabled():
            sections.append(self._build_merge_section())
        sections.append(self._build_attach_section())
        sections.append(self._build_final_section())
        for i, grp in enumerate(sections, 1):
            grp.setTitle(f"Step {i}：{grp.title()}")
            layout.addWidget(grp)
        layout.addStretch()

        scroll.setWidget(inner)
        return scroll
```

`_build_step1`メソッドの1行目 `grp = QGroupBox("Step 1：宛先条件")` を以下に置き換える:

```python
        grp = QGroupBox("宛先条件")
```

`_build_step2`メソッドの1行目 `grp = QGroupBox("Step 2：テンプレート・署名選択")` を以下に置き換える:

```python
        grp = QGroupBox("テンプレート・署名選択")
```

`_build_step3`メソッドを以下のようにリネーム・変更する（メソッド名と1行目のタイトルのみ変更、中身は変更しない）:

```python
    def _build_merge_section(self) -> QGroupBox:
        grp = QGroupBox("差し込みデータ（任意）")
        layout = QVBoxLayout(grp)
        btn = QPushButton("CSV/Excelをインポート")
        btn.clicked.connect(self._import_merge)
        self._merge_status = QLabel("（未読み込み — col1〜col5は空で送信）")
        layout.addWidget(btn)
        layout.addWidget(self._merge_status)
        return grp
```

`_build_step4`メソッドの1行目 `grp = QGroupBox("Step 4：添付ファイル（任意）")` を以下に置き換え、メソッド名を`_build_attach_section`にリネームする:

```python
    def _build_attach_section(self) -> QGroupBox:
        grp = QGroupBox("添付ファイル（任意）")
```

`_build_step5`メソッドの1行目 `grp = QGroupBox("Step 5：最終確認・送信")` を以下に置き換え、メソッド名を`_build_final_section`にリネームする:

```python
    def _build_final_section(self) -> QGroupBox:
        grp = QGroupBox("最終確認・送信")
```

`_clear_all`メソッド内の `self._merge_status.setText("（未読み込み — col1〜col5は空で送信）")` の行を以下に置き換える:

```python
        if hasattr(self, "_merge_status"):
            self._merge_status.setText("（未読み込み — col1〜col5は空で送信）")
```

- [ ] **Step 4: テストを実行して成功を確認**

Run: `pytest tests/test_send_tab_step_numbering.py tests/test_send_tab_list_mode.py tests/test_send_tab_placeholder.py tests/test_send_tab_save_template.py -v`
Expected: PASS（既存タスクのテストも引き続き通ること）

- [ ] **Step 5: コミット**

```bash
git add app/ui/send_tab.py tests/test_send_tab_step_numbering.py
git commit -m "feat: 送信タブのステップ番号を動的採番にし差し込みデータを開発者フラグ化"
```

---

## Task 5: テンプレートタブのプレースホルダーを開発者フラグで統一

**Files:**
- Modify: `app/ui/template_tab.py`（import、`_PLACEHOLDERS`定義、`_build`内のプレースホルダーループ）
- Test: `tests/test_template_tab_placeholder_flag.py`（新規）

**Interfaces:**
- Consumes: なし（送信タブと同名だが独立した実装。`os.environ.get("CCI_MAIL_DEV_TOOLS")`を直接参照）

- [ ] **Step 1: 失敗するテストを書く**

```python
# tests/test_template_tab_placeholder_flag.py
from PyQt6.QtWidgets import QPushButton


class _FakeSession:
    def close(self):
        pass


def _placeholder_labels(tab):
    return [b.text() for b in tab.findChildren(QPushButton) if b.text().startswith("{")]


def test_merge_placeholders_hidden_without_dev_flag(qtbot, monkeypatch):
    monkeypatch.delenv("CCI_MAIL_DEV_TOOLS", raising=False)
    monkeypatch.setattr("app.ui.template_tab.get_session", lambda: _FakeSession())
    monkeypatch.setattr("app.ui.template_tab.get_templates", lambda s: [])
    monkeypatch.setattr("app.ui.template_tab.get_signatures", lambda s: [])

    from app.ui.template_tab import TemplateTab
    tab = TemplateTab()
    qtbot.addWidget(tab)

    labels = _placeholder_labels(tab)
    assert "{col1}" not in labels
    assert "{事業所名}" in labels


def test_merge_placeholders_shown_with_dev_flag(qtbot, monkeypatch):
    monkeypatch.setenv("CCI_MAIL_DEV_TOOLS", "1")
    monkeypatch.setattr("app.ui.template_tab.get_session", lambda: _FakeSession())
    monkeypatch.setattr("app.ui.template_tab.get_templates", lambda s: [])
    monkeypatch.setattr("app.ui.template_tab.get_signatures", lambda s: [])

    from app.ui.template_tab import TemplateTab
    tab = TemplateTab()
    qtbot.addWidget(tab)

    labels = _placeholder_labels(tab)
    assert "{col1}" in labels
```

- [ ] **Step 2: テストを実行して失敗を確認**

Run: `pytest tests/test_template_tab_placeholder_flag.py -v`
Expected: FAIL — `assert "{col1}" not in labels`（現状は常に`{col1}`〜`{col5}`が表示されるため）

- [ ] **Step 3: `_PLACEHOLDERS`を開発者フラグ制御に変更**

`app/ui/template_tab.py`冒頭のimportとモジュール定数部分を以下に置き換える:

```python
# app/ui/template_tab.py
import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QListWidget, QListWidgetItem, QPushButton,
    QFormLayout, QLineEdit, QTextEdit, QComboBox,
    QLabel, QGroupBox, QMessageBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeySequence, QShortcut
from app.database.connection import get_session
from app.services.template_service import (
    get_templates, create_template, update_template, delete_template
)
from app.services.signature_service import get_signatures

_BASE_PLACEHOLDERS = ["{事業所名}", "{役職名}", "{氏名}", "{会議所役職名}"]
_MERGE_PLACEHOLDERS = ["{col1}", "{col2}", "{col3}", "{col4}", "{col5}"]


def _dev_tools_enabled() -> bool:
    return os.environ.get("CCI_MAIL_DEV_TOOLS") == "1"
```

`_build`メソッド内の`ph_grp`構築部分、`for ph in _PLACEHOLDERS:`の行を含むブロックを以下に置き換える:

```python
        ph_grp = QGroupBox("使用可能なプレースホルダー（クリックで本文に挿入）")
        ph_layout = QVBoxLayout(ph_grp)
        btn_row = QHBoxLayout()
        placeholders = list(_BASE_PLACEHOLDERS)
        if _dev_tools_enabled():
            placeholders += _MERGE_PLACEHOLDERS
        for ph in placeholders:
            btn = QPushButton(ph)
            btn.setFlat(True)
            btn.setStyleSheet(
                "font-size: 12px; color: #1E40AF; padding: 2px 6px;"
                "border: 1px solid #BFDBFE; border-radius: 3px;")
            btn.clicked.connect(lambda checked, p=ph: self._insert_placeholder(p))
            btn_row.addWidget(btn)
        btn_row.addStretch()
        ph_layout.addLayout(btn_row)
        ph_layout.addWidget(QLabel(
            "差し込みデータ: {col1}〜{col5}は送信時にCSV/Excelからインポートした値に置換されます"))
        right_layout.addWidget(ph_grp)
```

- [ ] **Step 4: テストを実行して成功を確認**

Run: `pytest tests/test_template_tab_placeholder_flag.py -v`
Expected: PASS

- [ ] **Step 5: コミット**

```bash
git add app/ui/template_tab.py tests/test_template_tab_placeholder_flag.py
git commit -m "feat: テンプレートタブのプレースホルダーを開発者フラグで統一"
```

---

## Task 6: Step4（添付ファイル）を使用時のみ展開表示に

**Files:**
- Modify: `app/ui/send_tab.py`（`_build_attach_section`、`_clear_all`）
- Test: `tests/test_send_tab_attach_toggle.py`（新規）

**Interfaces:**
- Produces: `SendTab._chk_use_attach`（`QCheckBox`）, `SendTab._attach_body`（`QWidget`）, `SendTab._on_use_attach_toggled(checked: bool) -> None`

- [ ] **Step 1: 失敗するテストを書く**

```python
# tests/test_send_tab_attach_toggle.py
class _FakeSession:
    def close(self):
        pass


def _patch_common(monkeypatch):
    monkeypatch.setattr("app.ui.send_tab.get_session", lambda: _FakeSession())
    monkeypatch.setattr("app.ui.send_tab.get_positions", lambda s: [])
    monkeypatch.setattr("app.ui.send_tab.get_committees", lambda s: [])
    monkeypatch.setattr("app.ui.send_tab.get_members", lambda s: [])
    monkeypatch.setattr("app.ui.send_tab.get_templates", lambda s: [])
    monkeypatch.setattr("app.ui.send_tab.get_signatures", lambda s: [])
    monkeypatch.setattr("app.ui.send_tab.get_default_signature", lambda s: None)


def test_attach_body_hidden_until_checked(qtbot, monkeypatch):
    _patch_common(monkeypatch)
    from app.ui.send_tab import SendTab
    tab = SendTab(staff_name="担当者A")
    qtbot.addWidget(tab)
    tab.show()

    assert tab._chk_use_attach.isChecked() is False
    assert tab._attach_body.isVisible() is False

    tab._chk_use_attach.setChecked(True)
    assert tab._attach_body.isVisible() is True


def test_clear_all_resets_attach_checkbox(qtbot, monkeypatch):
    _patch_common(monkeypatch)
    from app.ui.send_tab import SendTab
    tab = SendTab(staff_name="担当者A")
    qtbot.addWidget(tab)
    tab.show()

    tab._chk_use_attach.setChecked(True)
    tab._clear_all()
    assert tab._chk_use_attach.isChecked() is False
    assert tab._attach_body.isVisible() is False
```

- [ ] **Step 2: テストを実行して失敗を確認**

Run: `pytest tests/test_send_tab_attach_toggle.py -v`
Expected: FAIL — `AttributeError: 'SendTab' object has no attribute '_chk_use_attach'`

- [ ] **Step 3: `_build_attach_section`をチェックボックス展開方式に変更**

`_build_attach_section`メソッド全体（Task 4でリネーム済み）を以下に置き換える:

```python
    def _build_attach_section(self) -> QGroupBox:
        grp = QGroupBox("添付ファイル（任意）")
        layout = QVBoxLayout(grp)

        self._chk_use_attach = QCheckBox("添付ファイルを使用する")
        self._chk_use_attach.toggled.connect(self._on_use_attach_toggled)
        layout.addWidget(self._chk_use_attach)

        self._attach_body = QWidget()
        body_layout = QVBoxLayout(self._attach_body)
        body_layout.setContentsMargins(0, 0, 0, 0)

        common_row = QHBoxLayout()
        btn_common = QPushButton("全社共通ファイルを選択")
        btn_common.clicked.connect(self._select_common_attach)
        btn_common_clear = QPushButton("クリア")
        btn_common_clear.setFixedWidth(52)
        btn_common_clear.clicked.connect(self._clear_common_attach)
        self._common_label = QLabel("（未選択）")
        self._common_label.setWordWrap(True)
        common_row.addWidget(btn_common)
        common_row.addWidget(btn_common_clear)
        common_row.addWidget(self._common_label, 1)
        body_layout.addLayout(common_row)

        body_layout.addWidget(QLabel(
            "会社別：会員番号に対応するファイルをフォルダから自動で添付します"))
        folder_row = QHBoxLayout()
        btn_folder = QPushButton("フォルダを選択")
        btn_folder.clicked.connect(self._select_indiv_folder)
        btn_folder_clear = QPushButton("クリア")
        btn_folder_clear.setFixedWidth(52)
        btn_folder_clear.clicked.connect(self._clear_indiv_folder)
        self._folder_label = QLabel("（未選択）")
        self._folder_label.setWordWrap(True)
        folder_row.addWidget(btn_folder)
        folder_row.addWidget(btn_folder_clear)
        folder_row.addWidget(self._folder_label, 1)
        body_layout.addLayout(folder_row)

        rule_row = QHBoxLayout()
        rule_row.addWidget(QLabel("ファイル名:"))
        self._rule_edit = QLineEdit("{会員番号}.pdf")
        self._rule_edit.setToolTip(
            "{会員番号} の部分に各会員番号が入ります。\n例: 会員番号が A001 なら → A001.pdf")
        rule_row.addWidget(self._rule_edit)
        btn_match = QPushButton("添付ファイルを確認・設定")
        btn_match.clicked.connect(self._check_matching)
        rule_row.addWidget(btn_match)
        body_layout.addLayout(rule_row)

        match_row = QHBoxLayout()
        self._match_label = QLabel("")
        match_row.addWidget(self._match_label)
        self._btn_show_attach = QPushButton("一覧を確認")
        self._btn_show_attach.setVisible(False)
        self._btn_show_attach.clicked.connect(self._show_attach_list)
        match_row.addWidget(self._btn_show_attach)
        body_layout.addLayout(match_row)

        layout.addWidget(self._attach_body)
        self._attach_body.setVisible(False)

        return grp

    def _on_use_attach_toggled(self, checked: bool):
        self._attach_body.setVisible(checked)
```

`_clear_all`メソッド内、`self._clear_common_attach()` の行の直前に以下を追加する:

```python
        self._chk_use_attach.setChecked(False)
```

- [ ] **Step 4: テストを実行して成功を確認**

Run: `pytest tests/test_send_tab_attach_toggle.py -v`
Expected: PASS

- [ ] **Step 5: コミット**

```bash
git add app/ui/send_tab.py tests/test_send_tab_attach_toggle.py
git commit -m "feat: 送信タブStep4を使用時のみ展開表示にする"
```

---

## Task 7: 個別添付ファイルのワイルドカードマッチングと複数ファイル対応

**Files:**
- Modify: `app/ui/send_tab.py`（`_build_attach_section`の`_rule_edit`部分、`_check_matching`、`_build_targets`のattach_map構築）
- Modify: `app/ui/dialogs/attach_confirm_dialog.py`（複数ファイル表示）
- Test: `tests/test_send_tab_wildcard_match.py`（新規）

**Interfaces:**
- Consumes: `AttachConfirmDialog(member_attach_list: list[dict], parent=None)`の`member_attach_list`要素が`filepath`（単数str）から`filepaths`（`list[str]`）に変わる
- Produces: `_attach_list`各要素の`filepaths: list[str]`（旧`filepath: str`を置き換え）

- [ ] **Step 1: 失敗するテストを書く**

```python
# tests/test_send_tab_wildcard_match.py
import os
from PyQt6.QtWidgets import QDialog


class _Email:
    def __init__(self, address):
        self.address = address


class _Member:
    def __init__(self, id, member_number, org_name):
        self.id = id
        self.member_number = member_number
        self.organization_name = org_name
        self.organization_kana = ""
        self.name = "テスト太郎"
        self.name_kana = ""
        self.title = ""
        self.position = None
        self.email_addresses = [_Email(f"{member_number}@example.com")]


class _FakeSession:
    def close(self):
        pass


def _patch_common(monkeypatch):
    monkeypatch.setattr("app.ui.send_tab.get_session", lambda: _FakeSession())
    monkeypatch.setattr("app.ui.send_tab.get_positions", lambda s: [])
    monkeypatch.setattr("app.ui.send_tab.get_committees", lambda s: [])
    monkeypatch.setattr("app.ui.send_tab.get_templates", lambda s: [])
    monkeypatch.setattr("app.ui.send_tab.get_signatures", lambda s: [])
    monkeypatch.setattr("app.ui.send_tab.get_default_signature", lambda s: None)


def test_wildcard_matching_attaches_multiple_files_per_member(qtbot, monkeypatch, tmp_path):
    members = [_Member(1, "A001", "org1"), _Member(2, "A002", "org2")]
    _patch_common(monkeypatch)
    monkeypatch.setattr("app.ui.send_tab.get_members", lambda s: members)

    (tmp_path / "A001_請求書.pdf").write_text("dummy")
    (tmp_path / "A001_確認書_org1.pdf").write_text("dummy")
    (tmp_path / "A002_他社ファイル.pdf").write_text("dummy")

    from app.ui.send_tab import SendTab
    tab = SendTab(staff_name="担当者A")
    qtbot.addWidget(tab)

    tab._recipient.set_checks_by_member_ids({1, 2})
    tab._individual_folder = str(tmp_path)
    tab._rule_edit.setText("{会員番号}_*.pdf")

    monkeypatch.setattr(QDialog, "exec", lambda self: True)

    tab._check_matching()

    by_number = {r["member_number"]: r for r in tab._attach_list}
    assert sorted(os.path.basename(p) for p in by_number["A001"]["filepaths"]) == [
        "A001_確認書_org1.pdf", "A001_請求書.pdf"]
    assert by_number["A001"]["found"] is True
    assert by_number["A002"]["filepaths"] == []
    assert by_number["A002"]["found"] is False


def test_build_targets_passes_all_matched_files(qtbot, monkeypatch):
    members = [_Member(1, "A001", "org1")]
    _patch_common(monkeypatch)
    monkeypatch.setattr("app.ui.send_tab.get_members", lambda s: members)
    monkeypatch.setattr(
        "app.ui.send_tab.compile_send_targets",
        lambda **kwargs: kwargs["attach_map"])

    from app.ui.send_tab import SendTab
    tab = SendTab(staff_name="担当者A")
    qtbot.addWidget(tab)
    tab._recipient.set_checks_by_member_ids({1})
    tab._attach_list = [{
        "member_number": "A001", "org_name": "org1", "to_address": "a@example.com",
        "filepaths": ["/tmp/A001_請求書.pdf", "/tmp/A001_確認書_org1.pdf"],
        "found": True,
    }]

    result = tab._build_targets()
    assert result["A001"] == ["/tmp/A001_請求書.pdf", "/tmp/A001_確認書_org1.pdf"]
```

- [ ] **Step 2: テストを実行して失敗を確認**

Run: `pytest tests/test_send_tab_wildcard_match.py -v`
Expected: FAIL — `KeyError: 'filepaths'`（現状は完全一致・単一`filepath`のため）

- [ ] **Step 3: `_check_matching`・`_build_targets`・`_rule_edit`をワイルドカード対応に変更**

`_build_attach_section`メソッド内の`self._rule_edit`定義2行を以下に置き換える:

```python
        self._rule_edit = QLineEdit("{会員番号}_*.pdf")
        self._rule_edit.setToolTip(
            "{会員番号} の直後にアンダースコアを挟んだ命名を推奨します。\n"
            "例: A001_請求書.pdf、A001_確認書_○○商事.pdf\n"
            "* は任意の文字列にマッチします（ワイルドカード）。")
```

`_check_matching`メソッド全体を以下に置き換える:

```python
    def _check_matching(self):
        if not self._individual_folder:
            QMessageBox.warning(self, "エラー", "フォルダを先に選択してください。")
            return
        members = self._recipient.get_selected_members()
        if not members:
            QMessageBox.warning(self, "エラー", "宛先を先に選択してください。")
            return
        rule = self._rule_edit.text().strip()
        attach_list = []
        for m in members:
            to_addr = m.email_addresses[0].address if m.email_addresses else ""
            pattern = os.path.join(
                self._individual_folder,
                rule.replace("{会員番号}", glob.escape(m.member_number)))
            matched = sorted(glob.glob(pattern))
            attach_list.append({
                "member_number": m.member_number,
                "org_name":      m.organization_name,
                "to_address":    to_addr,
                "filepaths":     matched,
                "found":         len(matched) > 0,
            })
        from app.ui.dialogs.attach_confirm_dialog import AttachConfirmDialog
        dlg = AttachConfirmDialog(attach_list, parent=self)
        if dlg.exec():
            self._attach_list = attach_list
            found = sum(1 for r in self._attach_list if r["found"])
            missing = len(self._attach_list) - found
            status = f"設定済み: {found}/{len(self._attach_list)} 件"
            if missing:
                status += f"（{missing}件はファイルなし→添付スキップ）"
            self._match_label.setText(status)
            self._btn_show_attach.setVisible(True)
        else:
            self._attach_list = []
            self._match_label.setText("（添付設定をクリアしました）")
            self._btn_show_attach.setVisible(False)
```

`_build_targets`メソッド内の`attach_map`構築部分を以下に置き換える:

```python
        attach_map: dict[str, list[str]] = {
            r["member_number"]: r["filepaths"]
            for r in self._attach_list if r["found"]
        }
```

`app/ui/dialogs/attach_confirm_dialog.py`の`_build`メソッド内、`for r in self._list:`ループの中身を以下に置き換える:

```python
        for r in self._list:
            row = self._table.rowCount()
            self._table.insertRow(row)
            self._table.setItem(row, 0, QTableWidgetItem(r["org_name"]))
            self._table.setItem(row, 1, QTableWidgetItem(r["member_number"]))
            self._table.setItem(row, 2, QTableWidgetItem(r["to_address"]))
            filepaths = r["filepaths"]
            fname = ", ".join(os.path.basename(p) for p in filepaths) if filepaths else "-"
            self._table.setItem(row, 3, QTableWidgetItem(fname))
            found_item = QTableWidgetItem("○" if r["found"] else "×")
            if not r["found"]:
                found_item.setForeground(QColor("#DC2626"))
            self._table.setItem(row, 4, found_item)
```

- [ ] **Step 4: テストを実行して成功を確認**

Run: `pytest tests/test_send_tab_wildcard_match.py -v`
Expected: PASS

- [ ] **Step 5: コミット**

```bash
git add app/ui/send_tab.py app/ui/dialogs/attach_confirm_dialog.py tests/test_send_tab_wildcard_match.py
git commit -m "feat: 個別添付ファイルをワイルドカードマッチング・複数ファイル添付に対応"
```

---

## Task 8: テスト送信ボタンにテスト送信先アドレスを表示

**Files:**
- Modify: `app/ui/send_tab.py`（`_build_final_section`、`refresh`、新規メソッド `_update_test_button_label`）
- Test: `tests/test_send_tab_test_button_label.py`（新規）

**Interfaces:**
- Produces: `SendTab._update_test_button_label() -> None`

- [ ] **Step 1: 失敗するテストを書く**

```python
# tests/test_send_tab_test_button_label.py
class _FakeSession:
    def close(self):
        pass


def _patch_common(monkeypatch, test_address=None):
    monkeypatch.setattr("app.ui.send_tab.get_session", lambda: _FakeSession())
    monkeypatch.setattr("app.ui.send_tab.get_positions", lambda s: [])
    monkeypatch.setattr("app.ui.send_tab.get_committees", lambda s: [])
    monkeypatch.setattr("app.ui.send_tab.get_members", lambda s: [])
    monkeypatch.setattr("app.ui.send_tab.get_templates", lambda s: [])
    monkeypatch.setattr("app.ui.send_tab.get_signatures", lambda s: [])
    monkeypatch.setattr("app.ui.send_tab.get_default_signature", lambda s: None)
    monkeypatch.setattr(
        "app.ui.send_tab.get_graph_config",
        lambda: {"test_address": test_address} if test_address else {})


def test_button_shows_unset_when_no_test_address(qtbot, monkeypatch):
    _patch_common(monkeypatch, test_address=None)
    from app.ui.send_tab import SendTab
    tab = SendTab(staff_name="担当者A")
    qtbot.addWidget(tab)
    assert tab._btn_test.text() == "テスト送信（未設定）"


def test_button_shows_address_when_configured(qtbot, monkeypatch):
    _patch_common(monkeypatch, test_address="test@example.com")
    from app.ui.send_tab import SendTab
    tab = SendTab(staff_name="担当者A")
    qtbot.addWidget(tab)
    assert tab._btn_test.text() == "test@example.com にテスト送信"


def test_refresh_updates_button_label(qtbot, monkeypatch):
    _patch_common(monkeypatch, test_address=None)
    from app.ui.send_tab import SendTab
    tab = SendTab(staff_name="担当者A")
    qtbot.addWidget(tab)
    assert tab._btn_test.text() == "テスト送信（未設定）"

    monkeypatch.setattr(
        "app.ui.send_tab.get_graph_config",
        lambda: {"test_address": "new@example.com"})
    tab.refresh()
    assert tab._btn_test.text() == "new@example.com にテスト送信"
```

- [ ] **Step 2: テストを実行して失敗を確認**

Run: `pytest tests/test_send_tab_test_button_label.py -v`
Expected: FAIL — `AttributeError: 'SendTab' object has no attribute '_btn_test'`

- [ ] **Step 3: `_build_final_section`・`refresh`を変更し`_update_test_button_label`を実装**

`_build_final_section`メソッド内、`btn_row = QHBoxLayout()`から`layout.addLayout(btn_row)`までのブロックを以下に置き換える:

```python
        btn_row = QHBoxLayout()
        self._btn_test = QPushButton("テスト送信（1通）")
        self._btn_test.clicked.connect(self._test_send)
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
        btn_row.addWidget(self._btn_test)
        btn_row.addWidget(btn_preview)
        btn_row.addStretch()
        btn_row.addWidget(self._btn_cancel)
        btn_row.addWidget(self._btn_send)
        layout.addLayout(btn_row)
```

`_build_final_section`メソッドの`return grp`の直前に以下を追加する:

```python
        self._update_test_button_label()
```

`refresh`メソッドを以下に置き換える:

```python
    def refresh(self):
        self._load_combos()
        self._update_test_button_label()
```

`_update_test_button_label`メソッドを`refresh`メソッドの直後に追加する:

```python
    def _update_test_button_label(self):
        graph_config = get_graph_config()
        addr = graph_config.get("test_address")
        self._btn_test.setText(f"{addr} にテスト送信" if addr else "テスト送信（未設定）")
```

- [ ] **Step 4: テストを実行して成功を確認**

Run: `pytest tests/test_send_tab_test_button_label.py -v`
Expected: PASS

- [ ] **Step 5: コミット**

```bash
git add app/ui/send_tab.py tests/test_send_tab_test_button_label.py
git commit -m "feat: テスト送信ボタンに設定済みテスト送信先アドレスを表示"
```

---

## 全体テスト実行（最終確認）

全タスク完了後、既存スイートを含めて回帰がないことを確認する。

Run: `pytest -v`
Expected: 既存テストすべて + 本計画で追加したテストすべてが PASS
