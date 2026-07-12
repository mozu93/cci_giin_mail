# 送信履歴の自動削除（1年保存） Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 送信済みから365日（1年）より古い送信ジョブ・送信明細を、アプリ起動時に自動削除する。

**Architecture:** `app/services/send_job_service.py` に `delete_old_jobs(session, days=365)` を追加し、`main.py` の起動フロー（ログイン成功後）から1回呼び出す。`SendJob` → `SendLog` は既存の `cascade="all, delete-orphan"` により、`SendJob` を削除するだけで関連 `SendLog` も自動的に削除される。新規モジュール・DBスキーマ変更・UI変更はなし。

**Tech Stack:** Python 3.11+, SQLAlchemy, pytest（`tests/conftest.py` の `db_session` フィクスチャ使用）

## Global Constraints

- 削除基準日は `SendJob.sent_at`（送信日時）。`sent_at` が `None`（下書き・未送信）のジョブは対象外。
- 削除実行時、確認ダイアログ・通知は一切出さない（黙って削除）。
- 削除処理で例外が発生してもアプリ起動をブロックしない。
- 既存の公開関数シグネチャ・DBスキーマは変更しない。追加のみ。
- 参照仕様: `docs/superpowers/specs/2026-07-12-send-history-retention-design.md`

---

## Task 1: `delete_old_jobs` サービス関数の実装

**Files:**
- Modify: `app/services/send_job_service.py`（`from datetime import datetime` を `from datetime import datetime, timedelta` に変更し、末尾に関数追加）
- Test: `tests/test_send_job_service.py`（追記）

**Interfaces:**
- Produces: `delete_old_jobs(session: Session, days: int = 365) -> int`（削除件数を返す）。Task 2 がこの関数を `main.py` から呼び出す。

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_send_job_service.py` の末尾に以下を追記する。

```python
from datetime import datetime, timedelta
from app.database.models import SendJob, SendLog
from app.services.send_job_service import delete_old_jobs


def test_delete_old_jobs_removes_jobs_older_than_one_year(db_session):
    tmpl, staff = _setup(db_session)
    old_job = create_job(db_session, "1年以上前のジョブ", tmpl.id, staff.id)
    old_job.sent_at = datetime.now() - timedelta(days=366)
    db_session.commit()

    deleted_count = delete_old_jobs(db_session, days=365)

    assert deleted_count == 1
    assert db_session.get(SendJob, old_job.id) is None


def test_delete_old_jobs_keeps_jobs_within_one_year(db_session):
    tmpl, staff = _setup(db_session)
    recent_job = create_job(db_session, "364日前のジョブ", tmpl.id, staff.id)
    recent_job.sent_at = datetime.now() - timedelta(days=364)
    db_session.commit()

    deleted_count = delete_old_jobs(db_session, days=365)

    assert deleted_count == 0
    assert db_session.get(SendJob, recent_job.id) is not None


def test_delete_old_jobs_keeps_drafts_without_sent_at(db_session):
    tmpl, staff = _setup(db_session)
    draft_job = create_job(db_session, "下書きジョブ", tmpl.id, staff.id)
    # sent_atはNoneのまま(create_jobはsent_atを設定しない)

    deleted_count = delete_old_jobs(db_session, days=365)

    assert deleted_count == 0
    assert db_session.get(SendJob, draft_job.id) is not None


def test_delete_old_jobs_cascades_to_logs(db_session):
    tmpl, staff = _setup(db_session)
    old_job = create_job(db_session, "1年以上前のジョブ", tmpl.id, staff.id)
    log = add_log(db_session, old_job.id, None, "a@example.com", "件名", "success")
    old_job.sent_at = datetime.now() - timedelta(days=400)
    db_session.commit()
    log_id = log.id

    delete_old_jobs(db_session, days=365)

    assert db_session.get(SendLog, log_id) is None
```

- [ ] **Step 2: テストを実行し、失敗することを確認する**

Run: `pytest tests/test_send_job_service.py -v`
Expected: `delete_old_jobs` が存在しないため `ImportError` で失敗する

- [ ] **Step 3: 最小実装を書く**

`app/services/send_job_service.py` の1行目を変更する。

```python
from datetime import datetime, timedelta
```

同ファイルの末尾に以下を追加する。

```python
def delete_old_jobs(session: Session, days: int = 365) -> int:
    """sent_atが基準日より古いSendJobを削除する（関連SendLogもcascadeで削除）。
    戻り値: 削除件数
    """
    cutoff = datetime.now() - timedelta(days=days)
    old_jobs = (session.query(SendJob)
                .filter(SendJob.sent_at.isnot(None))
                .filter(SendJob.sent_at < cutoff)
                .all())
    count = len(old_jobs)
    for job in old_jobs:
        session.delete(job)
    session.commit()
    return count
```

- [ ] **Step 4: テストを実行し、成功することを確認する**

Run: `pytest tests/test_send_job_service.py -v`
Expected: 全テストPASS（既存4件 + 新規4件 = 8件）

- [ ] **Step 5: コミット**

```bash
git add app/services/send_job_service.py tests/test_send_job_service.py
git commit -m "feat: 送信履歴の自動削除(1年保存)機能を追加"
```

---

## Task 2: アプリ起動時の呼び出し結線

**Files:**
- Modify: `main.py:91-96`（`LoginDialog` 承認後、`MainWindow` 作成前）

**Interfaces:**
- Consumes: `app.services.send_job_service.delete_old_jobs(session, days=365) -> int`（Task 1で実装済み）

- [ ] **Step 1: `main.py` を修正する**

`main.py` の該当箇所を以下のように変更する（変更前後を示す）。

変更前:
```python
    dlg = LoginDialog()
    if dlg.exec() != LoginDialog.DialogCode.Accepted:
        sys.exit(0)

    window = MainWindow(staff_name=dlg.staff_name(), readonly=dlg.readonly())
    window.show()
    sys.exit(app.exec())
```

変更後:
```python
    dlg = LoginDialog()
    if dlg.exec() != LoginDialog.DialogCode.Accepted:
        sys.exit(0)

    from app.database.connection import get_session
    from app.services.send_job_service import delete_old_jobs
    session = get_session()
    try:
        delete_old_jobs(session)
    except Exception:
        pass
    finally:
        session.close()

    window = MainWindow(staff_name=dlg.staff_name(), readonly=dlg.readonly())
    window.show()
    sys.exit(app.exec())
```

- [ ] **Step 2: 起動確認**

Run: `python main.py`
Expected: アプリが通常通り起動し、ログイン後にメインウィンドウが表示される（エラーダイアログが出ない）。手動確認のため、実行結果を目視で確認する。

- [ ] **Step 3: 既存テストスイート全体を実行し、デグレがないことを確認する**

Run: `pytest -v`
Expected: 全テストPASS

- [ ] **Step 4: コミット**

```bash
git add main.py
git commit -m "feat: アプリ起動時に古い送信履歴を自動削除する処理を結線"
```

---

## Self-Review Notes

- **Spec coverage:** 設計書の「削除関数」「呼び出し箇所」「テスト」「対象外」の各項目に対応するタスクを用意済み。エラーハンドリング（例外を握りつぶす）はTask 2 Step 1に反映済み。
- **Placeholder scan:** なし。全ステップに実コードを記載。
- **Type consistency:** `delete_old_jobs(session: Session, days: int = 365) -> int` はTask 1定義・Task 2利用で一致。
