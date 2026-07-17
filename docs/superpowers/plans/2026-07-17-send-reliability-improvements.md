# 送信信頼性改善 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** メール一斉送信処理（`_SendWorker` / `email_service.py`）の信頼性を高め、認証の途中停止・レート制限エラー・添付欠落の無言送信・不正メールアドレス・連続エラー時の暴走・中止時のログ欠落を解消する。

**Architecture:** 既存の `app/services/email_service.py`（Graph API通信）と `app/ui/send_tab.py`（`_SendWorker` QThread）を中心に、送信前チェック（トークン事前取得・添付サイズ検査・メール形式検証）と送信ループの堅牢化（レート制限リトライ・送信間隔・連続エラー中断・スキップログ記録）を追加する。新規ファイルは検証ユーティリティ1点のみで、既存構造は変更しない。

**Tech Stack:** Python 3.11+ / PyQt6 / SQLAlchemy / requests / msal（Task 7 のみ msal-extensions を追加）

## Global Constraints

- 対象範囲は「送信信頼性の改善」のみ。DBスキーマ変更を伴う配信停止フラグ機能は本計画に含めない（別計画）。
- Task 7（トークンキャッシュ暗号化）は新規依存ライブラリ `msal-extensions` を追加する。CLAUDE.md のルールにより依存関係の追加は事前承認が必要。**Task 7 の `pip install` 実行前に必ずユーザーに確認すること。**
- 既存の日本語UI文言・エラーメッセージのスタイル（「〜してください」「〜が見つかりません」等）を踏襲する。
- 新規ダイアログは追加しない。既存の `QMessageBox` パターンのみを使う。
- 全タスクは `pytest` で既存テストと合わせて実行し、退行がないことを確認する。
- 各タスクは前タスクの変更後のファイル状態を前提とする（本計画のコード例は「そのタスク時点で存在するはずのコード」を示す）。

---

### Task 1: `send_mail()` にレート制限リトライと事前取得トークン受け渡しを追加

**Files:**
- Modify: `app/services/email_service.py`
- Test: `tests/test_email_service.py`

**Interfaces:**
- Produces: `send_mail(graph_config: dict, to_address: str, subject: str, body: str, attachments: list[str] | None = None, access_token: str | None = None) -> None`
  - `access_token` が渡された場合は `get_access_token()` を呼ばない。
  - Graph API が `429` を返した場合、`Retry-After` ヘッダー（秒数、無ければ5秒）だけ待って最大3回まで自動リトライする。

- [ ] **Step 1: 失敗するテストを書く（access_token 受け渡し）**

`tests/test_email_service.py` の末尾に追記：

```python
class _FakeResponse:
    def __init__(self, status_code, text="", headers=None):
        self.status_code = status_code
        self.text = text
        self.headers = headers or {}


def test_send_mail_uses_provided_access_token_without_fetching(monkeypatch):
    from app.services import email_service

    def fail_get_token(graph_config):
        raise AssertionError("access_token指定時はget_access_tokenを呼んではいけない")

    monkeypatch.setattr(email_service, "get_access_token", fail_get_token)
    monkeypatch.setattr(email_service.requests, "post",
                         lambda *a, **k: _FakeResponse(202))

    email_service.send_mail({}, "to@example.com", "件名", "本文",
                            access_token="provided-token")


def test_send_mail_retries_on_429_then_succeeds(monkeypatch):
    from app.services import email_service

    responses = [_FakeResponse(429, headers={"Retry-After": "1"}), _FakeResponse(202)]
    sleep_calls = []

    monkeypatch.setattr(email_service.requests, "post",
                         lambda *a, **k: responses.pop(0))
    monkeypatch.setattr(email_service.time, "sleep",
                         lambda s: sleep_calls.append(s))

    email_service.send_mail({}, "to@example.com", "件名", "本文",
                            access_token="token")

    assert sleep_calls == [1]


def test_send_mail_raises_after_max_429_retries(monkeypatch):
    from app.services import email_service

    monkeypatch.setattr(email_service.requests, "post",
                         lambda *a, **k: _FakeResponse(
                             429, text="rate limited", headers={"Retry-After": "1"}))
    monkeypatch.setattr(email_service.time, "sleep", lambda s: None)

    with pytest.raises(RuntimeError):
        email_service.send_mail({}, "to@example.com", "件名", "本文",
                                access_token="token")
```

- [ ] **Step 2: テストを実行して失敗を確認する**

Run: `pytest tests/test_email_service.py -v`
Expected: FAIL（`send_mail() got an unexpected keyword argument 'access_token'` および `email_service` に `time` 属性がない旨のエラー）

- [ ] **Step 3: `email_service.py` を実装する**

`app/services/email_service.py` の先頭 import に `time` を追加：

```python
import base64
import os
import time
import requests
import msal
from pathlib import Path
```

`send_mail()` を以下に置き換える（既存の該当関数を丸ごと置換）：

```python
_MAX_RATE_LIMIT_RETRIES = 3
_DEFAULT_RETRY_AFTER_SECONDS = 5


def send_mail(graph_config: dict, to_address: str, subject: str,
              body: str, attachments: list[str] | None = None,
              access_token: str | None = None) -> None:
    token = access_token or get_access_token(graph_config)
    payload = build_message(to_address, subject, body, attachments or [])
    headers = {"Authorization": f"Bearer {token}",
               "Content-Type": "application/json"}
    attempt = 0
    while True:
        resp = requests.post(
            "https://graph.microsoft.com/v1.0/me/sendMail",
            headers=headers,
            json=payload,
            timeout=30,
        )
        if resp.status_code in (200, 202):
            return
        if resp.status_code == 429 and attempt < _MAX_RATE_LIMIT_RETRIES:
            try:
                wait_seconds = int(resp.headers.get(
                    "Retry-After", _DEFAULT_RETRY_AFTER_SECONDS))
            except ValueError:
                wait_seconds = _DEFAULT_RETRY_AFTER_SECONDS
            time.sleep(wait_seconds)
            attempt += 1
            continue
        raise RuntimeError(
            f"送信失敗 ({resp.status_code}): {resp.text[:200]}"
        )
```

- [ ] **Step 4: テストを実行して成功を確認する**

Run: `pytest tests/test_email_service.py -v`
Expected: PASS（全テスト）

- [ ] **Step 5: コミット**

```bash
git add app/services/email_service.py tests/test_email_service.py
git commit -m "feat: send_mailに429リトライとトークン事前渡し対応を追加"
```

---

### Task 2: 送信バッチ開始前にトークンを一度だけ取得し、送信間隔を空ける

**Files:**
- Modify: `app/ui/send_tab.py`
- Modify: `tests/test_send_worker_cancel.py`
- Test: `tests/test_send_worker_access_token.py`（新規）
- Test: `tests/test_send_worker_send_interval.py`（新規）

**Interfaces:**
- Consumes: Task 1 の `send_mail(..., access_token=...)`
- Produces:
  - `_SendWorker.__init__(self, targets: list[dict], graph_config: dict, job_id: int, access_token: str)`（`access_token` 引数を追加）
  - モジュール定数 `_SEND_INTERVAL_SECONDS = 2.0`

**背景:** 現状 `_SendWorker` は送信1件ごとに `send_mail()` 内で `get_access_token()` を呼んでおり、トークン失効時にバックグラウンドスレッド内で対話認証（ブラウザ起動）が発生しうる。また送信間隔がなく、Graph APIのレート制限（約30通/分）にすぐ抵触する。

- [ ] **Step 1: 既存テストの呼び出しを新シグネチャに合わせて修正する**

`tests/test_send_worker_cancel.py` の該当行を修正：

```python
    worker = _SendWorker(targets, {}, job_id=1, access_token="token")
```

- [ ] **Step 2: 失敗するテストを書く（access_token 受け渡し）**

`tests/test_send_worker_access_token.py` を新規作成：

```python
from app.ui.send_tab import _SendWorker


class _FakeSession:
    def close(self):
        pass


def test_send_mail_receives_worker_access_token(monkeypatch):
    received = {}

    def fake_send_mail(graph_config, to_addr, subject, body, attachments,
                       access_token=None):
        received["access_token"] = access_token

    def fake_add_log(session, job_id, member_id, to_addr, subject, status, error=None):
        pass

    monkeypatch.setattr("app.ui.send_tab.send_mail", fake_send_mail)
    monkeypatch.setattr("app.ui.send_tab.add_log", fake_add_log)
    monkeypatch.setattr("app.ui.send_tab.get_session", lambda: _FakeSession())
    monkeypatch.setattr("app.ui.send_tab.time.sleep", lambda s: None)

    targets = [{"to_address": "a@example.com", "subject": "s", "body": "b",
                "org_name": "org", "member_id": 1, "attachments": []}]
    worker = _SendWorker(targets, {}, job_id=1, access_token="prefetched-token")
    worker.run()

    assert received["access_token"] == "prefetched-token"
```

- [ ] **Step 3: 送信間隔のテストを書く**

`tests/test_send_worker_send_interval.py` を新規作成：

```python
from app.ui.send_tab import _SendWorker, _SEND_INTERVAL_SECONDS


class _FakeSession:
    def close(self):
        pass


def test_sleeps_between_sends_but_not_after_last(monkeypatch):
    sleep_calls = []

    monkeypatch.setattr("app.ui.send_tab.send_mail", lambda *a, **k: None)
    monkeypatch.setattr("app.ui.send_tab.add_log", lambda *a, **k: None)
    monkeypatch.setattr("app.ui.send_tab.get_session", lambda: _FakeSession())
    monkeypatch.setattr("app.ui.send_tab.time.sleep",
                         lambda s: sleep_calls.append(s))

    targets = [
        {"to_address": f"a{i}@example.com", "subject": "s", "body": "b",
         "org_name": f"org{i}", "member_id": i, "attachments": []}
        for i in range(3)
    ]
    worker = _SendWorker(targets, {}, job_id=1, access_token="token")
    worker.run()

    assert sleep_calls == [_SEND_INTERVAL_SECONDS, _SEND_INTERVAL_SECONDS]
```

- [ ] **Step 4: テストを実行して失敗を確認する**

Run: `pytest tests/test_send_worker_access_token.py tests/test_send_worker_send_interval.py tests/test_send_worker_cancel.py -v`
Expected: FAIL（`_SendWorker() got an unexpected keyword argument 'access_token'`）

- [ ] **Step 5: `send_tab.py` を実装する**

ファイル先頭 import に `time` を追加し、`get_access_token` をimportに加える：

```python
import os
import glob
import time
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QScrollArea,
    QGroupBox, QFormLayout, QComboBox, QLabel,
    QPushButton, QCheckBox, QLineEdit, QTextEdit,
    QProgressBar, QFileDialog, QMessageBox, QInputDialog,
    QRadioButton, QButtonGroup,
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
from app.services.email_service import (
    compile_send_targets, send_mail, send_test_mail, get_access_token
)
from app.services.send_job_service import create_job, start_job, finish_job, add_log
from app.utils.app_config import get_graph_config
from app.ui.recipient_panel import RecipientPanel
```

`_SendWorker` クラス全体を以下に置き換える：

```python
_SEND_INTERVAL_SECONDS = 2.0


class _SendWorker(QThread):
    progress = pyqtSignal(int, int, str)
    finished = pyqtSignal(int, int, int)

    def __init__(self, targets: list[dict], graph_config: dict, job_id: int,
                access_token: str):
        super().__init__()
        self._targets = targets
        self._graph_config = graph_config
        self._job_id = job_id
        self._access_token = access_token
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
                              t["body"], t.get("attachments", []),
                              access_token=self._access_token)
                    add_log(session, self._job_id, t.get("member_id"),
                            to_addr, t["subject"], "success")
                    success += 1
                    self.progress.emit(i, total, f"送信済: {t['org_name']}")
                except Exception as e:
                    add_log(session, self._job_id, t.get("member_id"),
                            to_addr, t["subject"], "error", str(e))
                    error += 1
                    self.progress.emit(i, total, f"エラー: {t['org_name']} — {e}")
                if i < total and not self._cancelled:
                    time.sleep(_SEND_INTERVAL_SECONDS)
            self.finished.emit(success, error, skip)
        finally:
            session.close()
```

（このステップでは Task 6 の連続エラー中断はまだ追加しない。Task 6 で再度この `run()` を修正する。）

`_execute_send()` メソッド内、`if ret != QMessageBox.StandardButton.Yes: return` の直後・`session = get_session()` の直前に以下を挿入する：

```python
        try:
            access_token = get_access_token(graph_config)
        except Exception as e:
            QMessageBox.critical(self, "認証エラー", str(e))
            return

```

`self._worker = _SendWorker(targets, graph_config, job_id)` の行を以下に置き換える：

```python
        self._worker = _SendWorker(targets, graph_config, job_id, access_token)
```

- [ ] **Step 6: テストを実行して成功を確認する**

Run: `pytest tests/test_send_worker_access_token.py tests/test_send_worker_send_interval.py tests/test_send_worker_cancel.py -v`
Expected: PASS（全テスト）

- [ ] **Step 7: 既存のsend_tab関連テスト一式を実行し、退行がないことを確認する**

Run: `pytest tests/ -k send_tab -v`
Expected: PASS（全テスト）

- [ ] **Step 8: コミット**

```bash
git add app/ui/send_tab.py tests/test_send_worker_cancel.py tests/test_send_worker_access_token.py tests/test_send_worker_send_interval.py
git commit -m "feat: 送信バッチ開始前にトークンを1回だけ取得し、送信間隔を追加"
```

---

### Task 3: 添付ファイル欠落を無言スキップではなくエラー扱いにする

**Files:**
- Modify: `app/services/email_service.py`
- Test: `tests/test_email_service.py`

**Interfaces:**
- Produces: `build_message()` は添付パスが存在しない場合 `FileNotFoundError` を送出する（従来は無言で `continue` していた）。

**背景:** `build_message()` は添付ファイルが見つからない場合、無言でそのファイルを除外して添付なしのままメール本文を組み立てていた。マッチング確認から送信実行までの間にファイルが移動・削除されると、意図せず添付なしでメールが送信される。

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_email_service.py` に追記：

```python
def test_build_message_missing_attachment_raises(tmp_path):
    missing = str(tmp_path / "missing.pdf")
    with pytest.raises(FileNotFoundError):
        build_message("to@example.com", "件名", "本文", [missing])


def test_send_mail_raises_for_missing_attachment_without_http_call(tmp_path, monkeypatch):
    from app.services import email_service

    def fail_post(*args, **kwargs):
        raise AssertionError("添付ファイルが無い場合はHTTPリクエストを送ってはいけない")

    monkeypatch.setattr(email_service.requests, "post", fail_post)
    missing = str(tmp_path / "missing.pdf")

    with pytest.raises(FileNotFoundError):
        email_service.send_mail({}, "to@example.com", "件名", "本文",
                                attachments=[missing], access_token="token")
```

- [ ] **Step 2: テストを実行して失敗を確認する**

Run: `pytest tests/test_email_service.py -v -k missing_attachment`
Expected: FAIL（例外が送出されない）

- [ ] **Step 3: `build_message()` を実装する**

既存の `build_message()` 内、`for path in attachments:` ループの中身を以下に置き換える：

```python
def build_message(to_address: str, subject: str, body: str,
                  attachments: list[str]) -> dict:
    attachment_list = []
    for path in attachments:
        if not os.path.exists(path):
            raise FileNotFoundError(f"添付ファイルが見つかりません: {path}")
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
```

- [ ] **Step 4: テストを実行して成功を確認する**

Run: `pytest tests/test_email_service.py -v`
Expected: PASS（全テスト）

- [ ] **Step 5: コミット**

```bash
git add app/services/email_service.py tests/test_email_service.py
git commit -m "fix: 添付ファイル欠落時に無言送信せずエラーにする"
```

---

### Task 4: 添付ファイル合計サイズの上限チェック

**Files:**
- Modify: `app/services/email_service.py`
- Modify: `app/ui/send_tab.py`
- Test: `tests/test_email_service.py`
- Test: `tests/test_send_tab_attachment_size_limit.py`（新規）

**Interfaces:**
- Produces（`email_service.py`）:
  - `ATTACHMENT_SIZE_LIMIT_BYTES: int`（3MB）
  - `total_attachment_size(paths: list[str]) -> int`
- Produces（`send_tab.py`）:
  - `_split_oversized_targets(targets: list[dict]) -> tuple[list[dict], list[dict]]`（モジュール関数。戻り値は `(上限内, 上限超過)`）

**背景:** Microsoft Graph の `sendMail`（JSON直添付）はメール全体で約3MBが実用上限。超過すると413エラーで送信失敗する。送信実行前に検出し、対象から除外できるようにする。

- [ ] **Step 1: 失敗するテストを書く（email_service）**

`tests/test_email_service.py` に追記：

```python
def test_total_attachment_size_sums_existing_files(tmp_path):
    f1 = tmp_path / "a.txt"
    f1.write_bytes(b"x" * 100)
    f2 = tmp_path / "b.txt"
    f2.write_bytes(b"y" * 200)
    assert total_attachment_size([str(f1), str(f2)]) == 300


def test_total_attachment_size_ignores_missing_files(tmp_path):
    f1 = tmp_path / "a.txt"
    f1.write_bytes(b"x" * 50)
    missing = str(tmp_path / "missing.txt")
    assert total_attachment_size([str(f1), missing]) == 50
```

`tests/test_email_service.py` の先頭 import を以下に更新：

```python
import pytest
from app.services.email_service import (
    render_body, build_message, total_attachment_size
)
```

- [ ] **Step 2: テストを実行して失敗を確認する**

Run: `pytest tests/test_email_service.py -v -k total_attachment_size`
Expected: FAIL（`ImportError: cannot import name 'total_attachment_size'`）

- [ ] **Step 3: `email_service.py` に実装を追加する**

`build_message()` の直後に追加：

```python
ATTACHMENT_SIZE_LIMIT_BYTES = 3 * 1024 * 1024  # Graph sendMail直添付の実用上限（約3MB）


def total_attachment_size(paths: list[str]) -> int:
    return sum(os.path.getsize(p) for p in paths if os.path.exists(p))
```

- [ ] **Step 4: テストを実行して成功を確認する**

Run: `pytest tests/test_email_service.py -v`
Expected: PASS（全テスト）

- [ ] **Step 5: 失敗するテストを書く（send_tab）**

`tests/test_send_tab_attachment_size_limit.py` を新規作成：

```python
from app.ui.send_tab import _split_oversized_targets
from app.services.email_service import ATTACHMENT_SIZE_LIMIT_BYTES


def test_split_oversized_targets_separates_over_limit(tmp_path):
    small = tmp_path / "small.pdf"
    small.write_bytes(b"x" * 100)
    big = tmp_path / "big.pdf"
    big.write_bytes(b"y" * (ATTACHMENT_SIZE_LIMIT_BYTES + 1))

    targets = [
        {"org_name": "小さい会社", "attachments": [str(small)]},
        {"org_name": "大きい会社", "attachments": [str(big)]},
    ]
    ok, oversized = _split_oversized_targets(targets)
    assert [t["org_name"] for t in ok] == ["小さい会社"]
    assert [t["org_name"] for t in oversized] == ["大きい会社"]


def test_split_oversized_targets_empty_attachments_is_ok():
    targets = [{"org_name": "添付なし", "attachments": []}]
    ok, oversized = _split_oversized_targets(targets)
    assert len(ok) == 1
    assert oversized == []
```

- [ ] **Step 6: テストを実行して失敗を確認する**

Run: `pytest tests/test_send_tab_attachment_size_limit.py -v`
Expected: FAIL（`ImportError: cannot import name '_split_oversized_targets'`）

- [ ] **Step 7: `send_tab.py` に実装を追加する**

import 文を更新：

```python
from app.services.email_service import (
    compile_send_targets, send_mail, send_test_mail, get_access_token,
    total_attachment_size, ATTACHMENT_SIZE_LIMIT_BYTES,
)
```

`_SendWorker` クラス定義の直前（モジュールレベル）に追加：

```python
def _split_oversized_targets(targets: list[dict]) -> tuple[list[dict], list[dict]]:
    """添付合計サイズが上限を超えるターゲットを分離する。
    戻り値: (上限内のターゲット, 上限超過のターゲット)
    """
    ok, oversized = [], []
    for t in targets:
        if total_attachment_size(t.get("attachments", [])) > ATTACHMENT_SIZE_LIMIT_BYTES:
            oversized.append(t)
        else:
            ok.append(t)
    return ok, oversized
```

`_execute_send()` の冒頭を以下に置き換える（`targets = self._build_targets()` から最初の `if not targets:` チェックの直後まで）：

```python
    def _execute_send(self):
        targets = self._build_targets()
        if not targets:
            QMessageBox.warning(self, "エラー", "宛先を選択してください。")
            return

        targets, oversized = _split_oversized_targets(targets)
        if oversized:
            names = "\n".join(f"・{t['org_name']}" for t in oversized)
            ret = QMessageBox.question(
                self, "添付サイズ超過",
                f"以下の宛先は添付ファイル合計サイズが上限（3MB）を超えています。\n"
                f"送信対象から除外して続行しますか？\n\n{names}",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No)
            if ret != QMessageBox.StandardButton.Yes:
                return
            if not targets:
                QMessageBox.warning(self, "エラー", "送信可能な宛先がありません。")
                return

        job_name = self._job_name.text().strip()
```

（このあとの `if not job_name:` 以降は既存のまま変更しない。）

- [ ] **Step 8: テストを実行して成功を確認する**

Run: `pytest tests/test_send_tab_attachment_size_limit.py -v`
Expected: PASS（全テスト）

- [ ] **Step 9: 既存のsend_tab関連テスト一式を実行し、退行がないことを確認する**

Run: `pytest tests/ -k send_tab -v`
Expected: PASS（全テスト）

- [ ] **Step 10: コミット**

```bash
git add app/services/email_service.py app/ui/send_tab.py tests/test_email_service.py tests/test_send_tab_attachment_size_limit.py
git commit -m "feat: 添付ファイル合計サイズが上限を超える宛先を送信前に検出する"
```

---

### Task 5: メールアドレス形式検証（会員編集・インポート時）

**Files:**
- Create: `app/utils/validators.py`
- Modify: `app/ui/dialogs/member_edit_dialog.py`
- Modify: `app/services/import_service.py`
- Test: `tests/test_validators.py`（新規）
- Test: `tests/test_member_edit_dialog_email_validation.py`（新規）
- Test: `tests/test_import_service.py`

**Interfaces:**
- Produces: `is_valid_email(address: str) -> bool`（`app/utils/validators.py`）

**背景:** 会員編集ダイアログにもExcel/CSVインポート処理にもメールアドレスの形式検証がなく、誤入力は送信時エラーになって初めて判明する。

- [ ] **Step 1: 失敗するテストを書く（validators）**

`tests/test_validators.py` を新規作成：

```python
import pytest
from app.utils.validators import is_valid_email


@pytest.mark.parametrize("address", [
    "yamada@example.com",
    "somu.tantou@example.co.jp",
    "a+tag@example.com",
])
def test_is_valid_email_accepts_valid_addresses(address):
    assert is_valid_email(address) is True


@pytest.mark.parametrize("address", [
    "",
    "yamada",
    "yamada@",
    "@example.com",
    "yamada@example",
    "yamada @example.com",
    "yamada@ example.com",
])
def test_is_valid_email_rejects_invalid_addresses(address):
    assert is_valid_email(address) is False
```

- [ ] **Step 2: テストを実行して失敗を確認する**

Run: `pytest tests/test_validators.py -v`
Expected: FAIL（`ModuleNotFoundError: No module named 'app.utils.validators'`）

- [ ] **Step 3: `app/utils/validators.py` を実装する**

```python
import re

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def is_valid_email(address: str) -> bool:
    return bool(_EMAIL_RE.match(address))
```

- [ ] **Step 4: テストを実行して成功を確認する**

Run: `pytest tests/test_validators.py -v`
Expected: PASS（全テスト）

- [ ] **Step 5: 失敗するテストを書く（member_edit_dialog）**

`tests/test_member_edit_dialog_email_validation.py` を新規作成：

```python
from PyQt6.QtWidgets import QMessageBox


def test_save_blocks_invalid_email_format(qtbot, db_session, monkeypatch):
    from app.ui.dialogs.member_edit_dialog import MemberEditDialog
    dlg = MemberEditDialog(db_session, staff_name="担当者A")
    qtbot.addWidget(dlg)

    dlg._member_number.setText("A-200")
    dlg._org_name.setText("テスト商事")
    dlg._name.setText("山田太郎")
    dlg._email_rows[0][0].setText("invalid-address")

    warning_calls = []
    monkeypatch.setattr(
        QMessageBox, "warning",
        staticmethod(lambda *a, **k: warning_calls.append((a, k))))

    dlg._save()

    assert warning_calls, "不正なメールアドレスで警告が表示されていない"
    from app.services.member_service import get_members
    assert not any(m.member_number == "A-200" for m in get_members(db_session))


def test_save_accepts_valid_email_format(qtbot, db_session):
    from app.ui.dialogs.member_edit_dialog import MemberEditDialog
    dlg = MemberEditDialog(db_session, staff_name="担当者A")
    qtbot.addWidget(dlg)

    dlg._member_number.setText("A-201")
    dlg._org_name.setText("テスト商事2")
    dlg._name.setText("山田次郎")
    dlg._email_rows[0][0].setText("yamada@example.com")

    dlg._save()

    from app.services.member_service import get_members
    saved = next(m for m in get_members(db_session) if m.member_number == "A-201")
    assert saved.email_addresses[0].address == "yamada@example.com"
```

- [ ] **Step 6: テストを実行して失敗を確認する**

Run: `pytest tests/test_member_edit_dialog_email_validation.py -v`
Expected: FAIL（`test_save_blocks_invalid_email_format` が失敗＝不正アドレスでも保存されてしまう）

- [ ] **Step 7: `member_edit_dialog.py` を実装する**

import 文に追加（`from app.utils import to_hankaku_kana` の直後）：

```python
from app.utils.validators import is_valid_email
```

`_save()` メソッド内、`addresses` を組み立てるループの直後・`try:` の直前に挿入：

```python
        invalid = [a["address"] for a in addresses if not is_valid_email(a["address"])]
        if invalid:
            QMessageBox.warning(
                self, "入力エラー",
                "メールアドレスの形式が正しくありません:\n" + "\n".join(invalid))
            return
```

- [ ] **Step 8: テストを実行して成功を確認する**

Run: `pytest tests/test_member_edit_dialog_email_validation.py -v`
Expected: PASS（全テスト）

- [ ] **Step 9: 失敗するテストを書く（import_service）**

`tests/test_import_service.py` に追記：

```python
def test_import_members_skips_invalid_email_but_keeps_member(db_session):
    row = ["A-300", "テスト商事", "", "", "山田 太郎", "", "", "invalid-email", ""]
    result = import_members(db_session, [row], COLUMN_MAP, changed_by="管理者")

    assert result["created"] == 1
    assert any("メールアドレス" in e for e in result["errors"])

    from app.services.member_service import get_members
    members = get_members(db_session, active_only=False)
    member = next(m for m in members if m.member_number == "A-300")
    assert member.email_addresses == []
```

- [ ] **Step 10: テストを実行して失敗を確認する**

Run: `pytest tests/test_import_service.py -v -k invalid_email`
Expected: FAIL（不正なメールアドレスがそのまま登録されてしまう）

- [ ] **Step 11: `import_service.py` を実装する**

import 文に追加（`from app.utils import to_hankaku_kana` の直後）：

```python
from app.utils.validators import is_valid_email
```

`addresses` を組み立てるループを以下に置き換える：

```python
        addresses = []
        for n in range(1, 6):
            addr = _cell(row, f"email_{n}_address")
            if addr:
                if not is_valid_email(addr):
                    errors.append(
                        f"行{i} ({member_number}): メールアドレス{n}の形式が不正です（除外）: {addr}")
                    continue
                addresses.append({
                    "address":    addr,
                    "label":      _cell(row, f"email_{n}_label"),
                    "sort_order": n,
                })
```

- [ ] **Step 12: テストを実行して成功を確認する**

Run: `pytest tests/test_import_service.py -v`
Expected: PASS（全テスト）

- [ ] **Step 13: コミット**

```bash
git add app/utils/validators.py app/ui/dialogs/member_edit_dialog.py app/services/import_service.py tests/test_validators.py tests/test_member_edit_dialog_email_validation.py tests/test_import_service.py
git commit -m "feat: メールアドレスの形式検証を会員編集・インポート時に追加"
```

---

### Task 6: 連続エラー時の送信中断 + 未送信分のログ記録

**Files:**
- Modify: `app/ui/send_tab.py`
- Modify: `tests/test_send_worker_cancel.py`
- Test: `tests/test_send_worker_consecutive_error_abort.py`（新規）

**Interfaces:**
- Consumes: Task 2 で導入した `_SendWorker` の構造（`_SEND_INTERVAL_SECONDS` を使う送信ループ）
- Produces: モジュール定数 `_CONSECUTIVE_ERROR_LIMIT = 5`、モジュール関数 `_log_skipped_remaining(session, job_id, targets, start_index) -> int`

**背景:** 認証エラーやネットワーク断が起きても `_SendWorker` は全件を送信し続け、150件全部がエラーになりうる。また中止時・中断時に未送信分が `send_logs` に記録されず、送信履歴タブの件数が実際の対象数と食い違う。

- [ ] **Step 1: 失敗するテストを書く（連続エラー中断）**

`tests/test_send_worker_consecutive_error_abort.py` を新規作成：

```python
from app.ui.send_tab import _SendWorker, _CONSECUTIVE_ERROR_LIMIT


class _FakeSession:
    def close(self):
        pass


def test_aborts_after_consecutive_error_limit(monkeypatch):
    def fake_send_mail(graph_config, to_addr, subject, body, attachments,
                       access_token=None):
        raise RuntimeError("接続エラー")

    logged = []

    def fake_add_log(session, job_id, member_id, to_addr, subject, status, error=None):
        logged.append((to_addr, status))

    monkeypatch.setattr("app.ui.send_tab.send_mail", fake_send_mail)
    monkeypatch.setattr("app.ui.send_tab.add_log", fake_add_log)
    monkeypatch.setattr("app.ui.send_tab.get_session", lambda: _FakeSession())
    monkeypatch.setattr("app.ui.send_tab.time.sleep", lambda s: None)

    targets = [
        {"to_address": f"a{i}@example.com", "subject": "s", "body": "b",
         "org_name": f"org{i}", "member_id": i, "attachments": []}
        for i in range(_CONSECUTIVE_ERROR_LIMIT + 3)
    ]
    worker = _SendWorker(targets, {}, job_id=1, access_token="token")

    results = {}
    worker.finished.connect(lambda s, e, sk: results.update(success=s, error=e, skip=sk))
    worker.run()

    assert results["error"] == _CONSECUTIVE_ERROR_LIMIT
    assert results["skip"] == 3
    error_logs = [s for _, s in logged if s == "error"]
    skip_logs = [s for _, s in logged if s == "skip"]
    assert len(error_logs) == _CONSECUTIVE_ERROR_LIMIT
    assert len(skip_logs) == 3


def test_does_not_abort_when_errors_are_not_consecutive(monkeypatch):
    call_count = {"n": 0}

    def fake_send_mail(graph_config, to_addr, subject, body, attachments,
                       access_token=None):
        call_count["n"] += 1
        if call_count["n"] % 2 == 0:
            raise RuntimeError("時々失敗")

    monkeypatch.setattr("app.ui.send_tab.send_mail", fake_send_mail)
    monkeypatch.setattr("app.ui.send_tab.add_log", lambda *a, **k: None)
    monkeypatch.setattr("app.ui.send_tab.get_session", lambda: _FakeSession())
    monkeypatch.setattr("app.ui.send_tab.time.sleep", lambda s: None)

    n = _CONSECUTIVE_ERROR_LIMIT * 2 + 1
    targets = [
        {"to_address": f"a{i}@example.com", "subject": "s", "body": "b",
         "org_name": f"org{i}", "member_id": i, "attachments": []}
        for i in range(n)
    ]
    worker = _SendWorker(targets, {}, job_id=1, access_token="token")
    results = {}
    worker.finished.connect(lambda s, e, sk: results.update(success=s, error=e, skip=sk))
    worker.run()

    assert results["skip"] == 0
    assert results["success"] + results["error"] == n
```

- [ ] **Step 2: 失敗するテストを書く（中止時のスキップログ記録）**

`tests/test_send_worker_cancel.py` に追記：

```python
def test_cancel_logs_remaining_targets_as_skip(monkeypatch):
    logged = []

    def fake_send_mail(graph_config, to_addr, subject, body, attachments,
                       access_token=None):
        logged.append((to_addr, "sent"))
        if len(logged) == 1:
            worker.request_cancel()

    def fake_add_log(session, job_id, member_id, to_addr, subject, status, error=None):
        logged.append((to_addr, status))

    monkeypatch.setattr("app.ui.send_tab.send_mail", fake_send_mail)
    monkeypatch.setattr("app.ui.send_tab.add_log", fake_add_log)
    monkeypatch.setattr("app.ui.send_tab.get_session", lambda: _FakeSession())
    monkeypatch.setattr("app.ui.send_tab.time.sleep", lambda s: None)

    targets = [
        {"to_address": f"a{i}@example.com", "subject": "s", "body": "b",
         "org_name": f"org{i}", "member_id": i, "attachments": []}
        for i in range(5)
    ]
    worker = _SendWorker(targets, {}, job_id=1, access_token="token")
    worker.run()

    skip_logs = [addr for addr, status in logged if status == "skip"]
    assert skip_logs == ["a1@example.com", "a2@example.com",
                         "a3@example.com", "a4@example.com"]
```

- [ ] **Step 3: テストを実行して失敗を確認する**

Run: `pytest tests/test_send_worker_consecutive_error_abort.py tests/test_send_worker_cancel.py -v`
Expected: FAIL（`ImportError: cannot import name '_CONSECUTIVE_ERROR_LIMIT'`、および中止時のskipログが記録されない）

- [ ] **Step 4: `send_tab.py` を実装する**

`_SendWorker` クラス定義の直前（`_split_oversized_targets` の後）に追加：

```python
_CONSECUTIVE_ERROR_LIMIT = 5


def _log_skipped_remaining(session, job_id, targets, start_index) -> int:
    """targets[start_index:] を送信ログにskipとして記録する。戻り値: 記録した件数"""
    for t in targets[start_index:]:
        add_log(session, job_id, t.get("member_id"), t.get("to_address", ""),
                t.get("subject", ""), "skip")
    return len(targets) - start_index
```

`_SendWorker.run()` を以下に置き換える：

```python
    def run(self):
        session = get_session()
        try:
            success = error = skip = 0
            consecutive_errors = 0
            total = len(self._targets)
            for i, t in enumerate(self._targets, 1):
                if self._cancelled:
                    remaining = _log_skipped_remaining(
                        session, self._job_id, self._targets, i - 1)
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
                              t["body"], t.get("attachments", []),
                              access_token=self._access_token)
                    add_log(session, self._job_id, t.get("member_id"),
                            to_addr, t["subject"], "success")
                    success += 1
                    consecutive_errors = 0
                    self.progress.emit(i, total, f"送信済: {t['org_name']}")
                except Exception as e:
                    add_log(session, self._job_id, t.get("member_id"),
                            to_addr, t["subject"], "error", str(e))
                    error += 1
                    consecutive_errors += 1
                    self.progress.emit(i, total, f"エラー: {t['org_name']} — {e}")
                    if consecutive_errors >= _CONSECUTIVE_ERROR_LIMIT:
                        remaining = _log_skipped_remaining(
                            session, self._job_id, self._targets, i)
                        skip += remaining
                        self.progress.emit(
                            total, total,
                            f"エラーが{_CONSECUTIVE_ERROR_LIMIT}件連続したため中断しました"
                            f"（残り{remaining}件は未送信）")
                        break
                if i < total and not self._cancelled:
                    time.sleep(_SEND_INTERVAL_SECONDS)
            self.finished.emit(success, error, skip)
        finally:
            session.close()
```

- [ ] **Step 5: テストを実行して成功を確認する**

Run: `pytest tests/test_send_worker_consecutive_error_abort.py tests/test_send_worker_cancel.py -v`
Expected: PASS（全テスト）

- [ ] **Step 6: 送信関連テスト一式を実行し、退行がないことを確認する**

Run: `pytest tests/ -k send -v`
Expected: PASS（全テスト）

- [ ] **Step 7: コミット**

```bash
git add app/ui/send_tab.py tests/test_send_worker_consecutive_error_abort.py tests/test_send_worker_cancel.py
git commit -m "feat: 連続エラー時の送信中断と未送信分のスキップログ記録を追加"
```

---

### Task 7: トークンキャッシュの暗号化（msal-extensions）

> ⚠️ **このタスクは新規依存ライブラリ `msal-extensions` を追加する。CLAUDE.mdのルールにより依存関係の追加は事前承認が必要。`pip install` を実行する前に必ずユーザーに確認すること。**

**Files:**
- Modify: `requirements.txt`
- Modify: `app/services/email_service.py`
- Test: `tests/test_email_service_token_cache.py`（新規）

**Interfaces:**
- `get_access_token(graph_config: dict) -> str` のシグネチャ・戻り値は変更しない。内部実装のみ、平文の `msal.SerializableTokenCache` 手動読み書きから `msal_extensions.PersistedTokenCache`（Windows DPAPI暗号化）に置き換える。

**背景:** 現状 `~/.cci-mail/m365_token_cache.bin` に平文でトークンキャッシュが保存されている。同一ファイル・共有フォルダ運用ではないが、ローカルの他ユーザーからの読み取りリスクを下げるため暗号化する。

- [ ] **Step 1: ユーザーに依存ライブラリ追加の承認を得る**

ユーザーに「`msal-extensions` を依存関係に追加してよいか」を確認する。承認が得られてから次のステップに進む。

- [ ] **Step 2: 依存ライブラリを追加する**

`requirements.txt` に追記：

```
msal-extensions>=1.1.0
```

Run: `pip install msal-extensions>=1.1.0`

- [ ] **Step 3: 失敗するテストを書く**

`tests/test_email_service_token_cache.py` を新規作成：

```python
from unittest.mock import MagicMock
from app.services import email_service


def test_get_access_token_uses_encrypted_persistence(monkeypatch, tmp_path):
    cache_file = tmp_path / "cache.bin"
    monkeypatch.setattr(email_service, "_CACHE_FILE", cache_file)

    fake_persistence = object()
    build_calls = []

    def fake_build_encrypted_persistence(location):
        build_calls.append(location)
        return fake_persistence

    fake_cache = object()
    cache_calls = []

    def fake_persisted_cache(persistence):
        cache_calls.append(persistence)
        return fake_cache

    monkeypatch.setattr(email_service, "build_encrypted_persistence",
                        fake_build_encrypted_persistence)
    monkeypatch.setattr(email_service, "PersistedTokenCache", fake_persisted_cache)

    fake_app = MagicMock()
    fake_app.get_accounts.return_value = []
    fake_app.acquire_token_interactive.return_value = {"access_token": "abc123"}
    captured_kwargs = {}

    def fake_pca(**kwargs):
        captured_kwargs.update(kwargs)
        return fake_app

    monkeypatch.setattr(email_service.msal, "PublicClientApplication", fake_pca)

    token = email_service.get_access_token({"client_id": "cid", "tenant_id": "tid"})

    assert token == "abc123"
    assert build_calls == [str(cache_file)]
    assert cache_calls == [fake_persistence]
    assert captured_kwargs["token_cache"] is fake_cache
```

- [ ] **Step 4: テストを実行して失敗を確認する**

Run: `pytest tests/test_email_service_token_cache.py -v`
Expected: FAIL（`AttributeError: module 'app.services.email_service' has no attribute 'build_encrypted_persistence'`）

- [ ] **Step 5: `email_service.py` を実装する**

import 文に追加（`import msal` の直後）：

```python
from msal_extensions import build_encrypted_persistence, PersistedTokenCache
```

`get_access_token()` を以下に置き換える：

```python
def get_access_token(graph_config: dict) -> str:
    _CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    persistence = build_encrypted_persistence(str(_CACHE_FILE))
    cache = PersistedTokenCache(persistence)

    app = msal.PublicClientApplication(
        client_id=graph_config["client_id"],
        authority=f"https://login.microsoftonline.com/{graph_config['tenant_id']}",
        token_cache=cache,
    )

    result = None
    accounts = app.get_accounts()
    if accounts:
        result = app.acquire_token_silent(_SCOPES, account=accounts[0])

    if not result:
        result = app.acquire_token_interactive(scopes=_SCOPES)

    if not result or "access_token" not in result:
        desc = result.get("error_description", str(result)) if result else "不明なエラー"
        raise RuntimeError(f"Microsoft 365 認証に失敗しました: {desc}")

    return result["access_token"]
```

- [ ] **Step 6: テストを実行して成功を確認する**

Run: `pytest tests/test_email_service_token_cache.py -v`
Expected: PASS（全テスト）

- [ ] **Step 7: email_service関連テスト一式を実行し、退行がないことを確認する**

Run: `pytest tests/test_email_service.py tests/test_attendance_mail_service.py -v`
Expected: PASS（全テスト）

- [ ] **Step 8: コミット**

```bash
git add requirements.txt app/services/email_service.py tests/test_email_service_token_cache.py
git commit -m "feat: Microsoft 365トークンキャッシュをDPAPIで暗号化する"
```

---

## 最終確認

全タスク完了後、以下を実行して退行がないことを確認する。

```bash
pytest -v
```

Expected: 既存テスト＋本計画で追加したテストがすべてPASS。
