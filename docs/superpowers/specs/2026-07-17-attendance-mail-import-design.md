# 常議員会 出欠メール取り込み 設計書

**作成日：** 2026-07-17
**ステータス：** 承認待ち

---

## 1. 概要

常議員会の出欠連絡は、独自フォームからの申込内容が担当者個人のOutlookに転送されてくる。件名・本文は固定フォーマット（【出欠】【事業所名】等の括弧ラベル形式）で統一されている。

このメールをMicrosoft Graph API経由で読み取り、「事前入力」タブで選択中の会議に対して出欠（`AttendanceRecord`）を自動反映する機能を追加する。

- 対象は**常議員会の出欠連絡メールのみ**。委員会（総務・地域経済・中小小規模企業）の出欠連絡は申込フォーマットが未確定のため、今回はスコープ外とする。フォーマットが確定次第、同じ括弧ラベル解析の仕組みを流用して拡張する想定。
- メールは担当者個人宛（共有メールボックスではない）。複数職員が別々のPC・別々のMicrosoft 365アカウントでこの機能を使う可能性があるため、「処理済みメール」の判定はメールボックス側の状態（フォルダ移動等）ではなく、**アプリの共有DB**に記録する。
- 対象フォルダ名・対象件名（部分一致）は、実行の都度アプリ画面から指定できるようにする（Outlook側の仕分けルールで作るフォルダ名が固定されないため）。

既存の`Position`/`Committee`実装、`import_dialog.py`・`merge_preview_dialog.py`のプレビュー型ダイアログ、`_NoWheelComboBox`（`reception_widget.py`）等、既存パターンを踏襲する。

---

## 2. データモデル

### 2.1 `AttendanceRecord`に`notes`列を追加

メール本文の【備考】欄をそのまま保存する。

```python
notes = Column(Text, default="")
```

`app/database/connection.py`の`_migrate_sqlite` / `_migrate_postgresql`に、既存パターンと同様のALTER TABLE処理を追加する。

### 2.2 新規テーブル `ProcessedAttendanceMail`

取り込み済みメールを判定するための記録。`Base.metadata.create_all()`で自動生成されるため、マイグレーション対応は不要。

```python
class ProcessedAttendanceMail(Base):
    __tablename__ = "processed_attendance_mails"
    id = Column(Integer, primary_key=True)
    message_id = Column(String, unique=True, nullable=False)  # Graph APIのメッセージID
    meeting_id = Column(Integer, ForeignKey("meetings.id"), nullable=True)
    processed_at = Column(DateTime, nullable=False, default=datetime.now)
```

---

## 3. サービス層

### 3.1 `app/services/email_service.py`の変更

MSALのスコープに`Mail.Read`を追加し、1回のサインインで送信・読み取り両方の同意を得る。

```python
_SCOPES = ["https://graph.microsoft.com/Mail.Send",
           "https://graph.microsoft.com/Mail.Read"]
```

`get_access_token`は変更なし（スコープ定数の変更のみで両方カバーされる）。既存のサインイン済みユーザーは次回サインイン時に追加スコープの同意が必要になる（MSALが自動的に対話サインインへフォールバックする）。

### 3.2 新規 `app/services/attendance_mail_service.py`

```python
def fetch_messages(graph_config: dict, folder_name: str,
                    subject_filter: str, exclude_ids: set[str]) -> list[dict]:
    """Graph APIで指定フォルダ内のメールを取得する。
    folder_name（表示名）から /me/mailFolders でフォルダIDを解決し、
    /me/mailFolders/{id}/messages から取得（$top=200、150社分の想定件数に
    対して十分な余裕を持たせる。将来的に不足する場合は$skip等でページング
    追加）。subject_filterが空でなければ件名の部分一致でクライアント側
    フィルタする。exclude_ids に含まれる message_id（Graphのid）は除外する。
    戻り値は新しい順ではなく古い順。
    folder_nameに一致するフォルダが見つからない場合はValueErrorを送出し、
    呼び出し元（ダイアログ）でQMessageBoxのエラー表示に変換する。
    """

def parse_body(body_text: str) -> dict:
    """本文から【ラベル】: 値 形式を正規表現で抽出する。
    キー: status_raw, org_name, name, proxy_title, proxy_name,
    delegate_name, notes
    """

STATUS_MAP = {"出席": "出席", "出席(※代理)": "代理", "委任": "委任", "欠席": "欠席"}

def normalize_org_name(name: str) -> str:
    """突合用の正規化。株式会社/(株)/（株）/㈱ 等の除去、前後・内部の空白除去。"""

def match_member(session: Session, org_name: str) -> Member | None:
    """正規化した事業所名で一意に一致する会員を返す。0件/複数件はNoneを返す。"""

@dataclass
class AttendanceMailRow:
    message_id: str
    received_at: datetime
    org_name_raw: str
    name_raw: str
    status: str            # 出席/代理/委任/欠席（変換後）
    proxy_title: str
    proxy_name: str
    notes: str
    matched_member: Member | None
    existing_status: str | None   # 既にこの会議の出欠が登録済みならそのstatus

def build_preview(session: Session, meeting_id: int,
                   messages: list[dict]) -> list[AttendanceMailRow]:
    """メールをパース・突合し、同一会員宛の重複は受信日時が最新のものだけ残す
    （事業所名の正規化結果が同じものを同一人物とみなして重複排除する）。"""

def commit_rows(session: Session, meeting_id: int,
                rows: list[AttendanceMailRow],
                selected_member_by_row: dict[int, int]) -> dict:
    """selected_member_by_row で会員が確定している行だけ upsert_attendance を実行し、
    対象メールのmessage_idをProcessedAttendanceMailに記録する。
    戻り値: {"applied": int, "skipped": int}"""
```

`upsert_attendance`（`meeting_service.py`）に`notes`引数を追加し、`AttendanceRecord.notes`を更新するようにする。

---

## 4. UI変更

### 4.1 新規ダイアログ `app/ui/dialogs/attendance_mail_import_dialog.py`

`merge_preview_dialog.py`と同じ「プレビュー→確定」型のQDialog。

- 上部：フォルダ名入力欄（`QLineEdit`、前回値を`app_config.json`に保存し次回起動時も復元）、対象件名入力欄（同様に前回値を復元、空欄可）、「検索」ボタン
- 「検索」押下で`fetch_messages` → `build_preview`を実行し、テーブルに表示
  - 列：事業所名（メール記載）／氏名／出欠／代理役職・代理者名／備考／既存の登録（あれば「出席→欠席」のように変更前後を表示）／会員（`_NoWheelComboBox`、突合できた場合は自動選択済み、できなかった場合は空欄で未選択）
  - 会員未選択の行は目立つ配色（背景色）にする
- 下部：「反映」ボタン（会員が選択されている行だけ`commit_rows`を実行）、「キャンセル」ボタン
- 反映後、結果件数（適用件数／スキップ件数）を`QMessageBox`で表示してダイアログを閉じる

### 4.2 `app/ui/meeting_widgets/preentry_widget.py`

- ボタン行に「メールから出欠を取り込む」を追加（`readonly`時は非表示、`self._meeting_id`が未選択の場合は無効化）
- クリックで`AttendanceMailImportDialog`を`self._meeting_id`付きで開き、`accept`されたら`self._load_preentry()`で一覧を再読み込みする

---

## 5. テスト方針

既存パターン（pytest + pytest-qt、`db_session`フィクスチャ、Graph API呼び出しは`monkeypatch`でHTTPリクエスト関数を差し替え）に従う。

- `tests/test_attendance_mail_service.py`（新規）
  - `parse_body`：サンプル本文からの各項目抽出（出席/出席(※代理)/委任/欠席の4パターン）
  - `normalize_org_name`：株式会社表記ゆれの正規化
  - `match_member`：一意一致／0件／複数件のケース
  - `build_preview`：同一会員への複数メールで最新のみ残ること、既存登録がある場合に`existing_status`が入ること
  - `commit_rows`：選択済み行のみ`AttendanceRecord`に反映され、`ProcessedAttendanceMail`に記録されること。未選択行はスキップされること
- `tests/test_attendance_mail_import_dialog.py`（新規）
  - 突合できた行のコンボが自動選択済みであること
  - 未選択のまま「反映」した場合にその行がスキップされ、結果に反映されること
- `tests/test_meeting_service.py`（既存拡張）：`upsert_attendance`の`notes`引数

---

## 6. スコープ外

- 委員会（総務・地域経済・中小小規模企業）の出欠メール取り込み（フォーマット未確定のため）
- バックグラウンドでの自動巡回取り込み（手動「検索」ボタン方式のみ）
- 事業所名以外（メールアドレス等）による会員突合
- Outlook側フォルダの仕分けルール自体の自動設定（利用者が手動でOutlook側に仕分けルールを作る前提）
