# 送信履歴の自動削除（1年保存） 設計

## 背景・目的

現状、`SendJob`（送信ジョブ）・`SendLog`（送信明細）テーブルには削除・保存期限の仕組みが一切なく、無期限にデータベースへ蓄積され続ける。運用ルールとして「送信履歴は1年間保存し、それより古いものは自動的に削除する」ことを決定した。本設計はその自動削除機能を実装するためのもの。

## 要件（ユーザーとの合意事項）

1. **自動削除**：1年（365日）より古い送信履歴を自動的にデータベースから削除する。
2. **実行タイミング**：アプリ起動時（ログイン成功後）に毎回チェックして削除する。手動ボタンは設けない。
3. **基準日**：`SendJob.sent_at`（実際に送信した日時）を基準にする。`sent_at` が `None`（下書き・未送信）のジョブは削除対象外。
4. **通知**：削除実行時にユーザーへの確認ダイアログや通知は出さない（黙って削除する）。

## アーキテクチャ

既存の `app/services/send_job_service.py` にサービス関数を1つ追加し、`main.py` の起動フローから1回呼び出すだけのシンプルな構成とする。新規モジュールやスケジューラ、DBスキーマ変更は不要。

```
main.py (main() 内、ログイン成功後)
    → send_job_service.delete_old_jobs(session, days=365)
        → SendJob.sent_at < (今日 - 365日) かつ sent_at IS NOT NULL を検索
        → 該当 SendJob を削除（cascade="all, delete-orphan" により関連 SendLog も自動削除）
```

### 削除関数

`app/services/send_job_service.py` に以下を追加する。

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

- `SendJob` の `logs = relationship("SendLog", back_populates="job", cascade="all, delete-orphan")` が既に設定されているため、`SendJob` を削除するだけで対応する `SendLog` も自動的に削除される。追加のクエリは不要。
- 戻り値（削除件数）はテスト用途・将来のログ出力用に返すが、現時点でUIに表示する予定はない。

### 呼び出し箇所

`main.py` の `main()` 内、`LoginDialog` 承認後・`MainWindow` 表示前に1回呼び出す。

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
    pass  # 削除処理の失敗でアプリ起動を止めない
finally:
    session.close()

window = MainWindow(staff_name=dlg.staff_name(), readonly=dlg.readonly())
```

- 削除処理で例外が発生してもアプリ起動自体は継続させる（try/except で握りつぶし、通知もしない）。
- readonly ログイン（閲覧のみ権限）の場合でも削除は実行する。データ保存期間のルールは権限に関わらず一律適用するため。

## エラーハンドリング

- DB接続エラーなど致命的な例外が起きても、起動処理をブロックしない（catchして無視）。
- 削除処理自体に業務ロジック上のエラーケースはない（対象がなければ0件削除して終了）。

## テスト

`tests/test_send_job_service.py`（既存があれば追記、なければ新規）に以下を追加する。

- 366日前に `sent_at` を持つジョブ → `delete_old_jobs` 実行後に削除されていること
- 364日前に `sent_at` を持つジョブ → 削除されず残っていること
- `sent_at` が `None`（下書き）のジョブ → 削除されず残っていること
- 関連する `SendLog` も一緒に削除されていること（cascade確認）
- 戻り値が実際の削除件数と一致すること

`main.py` の起動時呼び出し自体はUIレベルの結線であり、既存のテスト方針上、単体テストの対象外とする（サービス関数のテストで担保する）。

## 対象外（YAGNIとして見送り）

- 削除前の確認ダイアログ・通知
- 手動削除ボタン
- 保存期間の設定画面（日数を設定で変更可能にする機能）
- QTimer等による定期実行（アプリ起動頻度を考えると起動時1回で十分）
