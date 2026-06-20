# cci-mail — 商工会議所メール配信システム 設計書

**作成日：** 2026-06-20  
**ステータス：** 承認済み

---

## 1. 概要

商工会議所が議員（約150社）に対してメールを一斉配信するためのデスクトップアプリケーション。  
宛先の絞り込み、メール本文テンプレート、差し込みデータ、共通・個別添付ファイル、送信履歴管理を備える。  
複数職員が共有フォルダ経由で共同利用する。

---

## 2. 技術スタック

| 要素 | 採用技術 |
|---|---|
| 言語 | Python 3.11+ |
| UI | PyQt6 |
| データベース | SQLAlchemy + SQLite |
| メール送信 | Microsoft Graph API（OAuth2 クライアントクレデンシャルフロー） |
| インポート | openpyxl / csv |
| 設定ファイル | JSON（app_config.json） |

---

## 3. ディレクトリ構成

```
cci-mail/
  main.py
  start.bat
  app_config.json          # SMTP設定等（DBとは別に管理）
  cci_mail.db              # SQLiteデータベース（共有フォルダに置く）
  app/
    database/
      __init__.py
      models.py            # 全モデル定義
      connection.py        # SQLAlchemy セッション管理
    services/
      member_service.py    # 名簿CRUD・履歴記録
      template_service.py  # テンプレートCRUD
      email_service.py     # Graph API送信
      send_job_service.py  # 送信ジョブ・ログ管理
      import_service.py    # Excel/CSVインポート
      signature_service.py # 署名CRUD
    ui/
      __init__.py
      main_window.py
      member_tab.py        # 名簿管理タブ
      template_tab.py      # テンプレートタブ
      send_tab.py          # メール送信タブ
      history_tab.py       # 送信履歴タブ
      settings_tab.py      # 設定タブ
      dialogs/
        member_edit_dialog.py    # 会員編集ダイアログ
        member_history_dialog.py # 変更履歴ダイアログ
        import_dialog.py         # インポート列マッピングダイアログ
        merge_preview_dialog.py  # 差し込みプレビューダイアログ
        attach_confirm_dialog.py # 個別添付確認ダイアログ
    utils/
      app_config.py        # 設定読み書き
  docs/
    superpowers/
      specs/
        2026-06-20-cci-mail-design.md
  tests/
  requirements.txt
```

---

## 4. データモデル

### `positions`（会議所役職マスタ）

| カラム | 型 | 制約 | 説明 |
|---|---|---|---|
| id | INTEGER | PK | |
| name | TEXT | NOT NULL | 例：会頭、副会頭、議員 |
| sort_order | INTEGER | NOT NULL | 表示順 |

### `members`（会員名簿）

| カラム | 型 | 制約 | 説明 |
|---|---|---|---|
| id | INTEGER | PK | |
| member_number | TEXT | UNIQUE, NOT NULL | 会員番号 |
| position_id | INTEGER | FK → positions | 会議所役職 |
| organization_name | TEXT | NOT NULL | 事業所名 |
| organization_kana | TEXT | | 事業所名フリガナ |
| title | TEXT | | 役職名（社長・専務等） |
| name | TEXT | NOT NULL | 氏名 |
| name_kana | TEXT | | 氏名フリガナ |
| notes | TEXT | | 備考 |
| is_active | BOOLEAN | DEFAULT TRUE | 有効フラグ |
| created_at | DATETIME | NOT NULL | |
| updated_at | DATETIME | NOT NULL | |

### `email_addresses`（メールアドレス：1社最大5件）

| カラム | 型 | 制約 | 説明 |
|---|---|---|---|
| id | INTEGER | PK | |
| member_id | INTEGER | FK → members | |
| address | TEXT | NOT NULL | メールアドレス |
| label | TEXT | | ラベル（本人・総務・代表等） |
| sort_order | INTEGER | NOT NULL | 1〜5 |

### `member_history`（名簿変更履歴）

| カラム | 型 | 制約 | 説明 |
|---|---|---|---|
| id | INTEGER | PK | |
| member_id | INTEGER | FK → members | |
| changed_at | DATETIME | NOT NULL | 変更日時 |
| changed_by | TEXT | NOT NULL | 変更した職員名 |
| change_reason | TEXT | NOT NULL | 変更理由 |
| snapshot | TEXT | NOT NULL | 変更前のデータ全体（JSON）。members全フィールド＋email_addresses配列を含む |

### `email_templates`（メールテンプレート）

| カラム | 型 | 制約 | 説明 |
|---|---|---|---|
| id | INTEGER | PK | |
| name | TEXT | NOT NULL | テンプレート名 |
| subject | TEXT | NOT NULL | 件名（差し込み記法対応） |
| body | TEXT | NOT NULL | 本文（差し込み記法対応） |
| signature_id | INTEGER | FK → signatures | デフォルト署名 |
| created_at | DATETIME | NOT NULL | |
| updated_at | DATETIME | NOT NULL | |

### `signatures`（メール署名）

| カラム | 型 | 制約 | 説明 |
|---|---|---|---|
| id | INTEGER | PK | |
| name | TEXT | NOT NULL | 署名名 |
| body | TEXT | NOT NULL | 署名本文 |
| is_default | BOOLEAN | DEFAULT FALSE | デフォルト使用するか |

### `staff`（職員マスタ）

| カラム | 型 | 制約 | 説明 |
|---|---|---|---|
| id | INTEGER | PK | |
| name | TEXT | NOT NULL | 職員名 |
| is_active | BOOLEAN | DEFAULT TRUE | 有効フラグ |

### `send_jobs`（送信ジョブ：1回の配信単位）

| カラム | 型 | 制約 | 説明 |
|---|---|---|---|
| id | INTEGER | PK | |
| name | TEXT | NOT NULL | ジョブ名（例：2026年6月 総会案内） |
| template_id | INTEGER | FK → email_templates | |
| staff_id | INTEGER | FK → staff | 操作者 |
| status | TEXT | NOT NULL | draft / sending / done / error |
| total_count | INTEGER | | 送信対象件数 |
| success_count | INTEGER | | 成功件数 |
| error_count | INTEGER | | エラー件数 |
| created_at | DATETIME | NOT NULL | |
| sent_at | DATETIME | | 送信完了日時 |

### `send_logs`（送信ログ：企業ごとの送信結果）

| カラム | 型 | 制約 | 説明 |
|---|---|---|---|
| id | INTEGER | PK | |
| job_id | INTEGER | FK → send_jobs | |
| member_id | INTEGER | FK → members | |
| to_address | TEXT | NOT NULL | 実際の送信先アドレス |
| subject | TEXT | NOT NULL | 実際に送信した件名 |
| status | TEXT | NOT NULL | success / error / skip |
| error_message | TEXT | | エラー内容 |
| sent_at | DATETIME | | |

---

## 5. 差し込みプレースホルダー仕様

メールテンプレートの件名・本文に以下のプレースホルダーを使用できる。

| プレースホルダー | 展開内容 |
|---|---|
| `{事業所名}` | members.organization_name |
| `{役職名}` | members.title |
| `{氏名}` | members.name |
| `{会議所役職名}` | positions.name |
| `{col1}` 〜 `{col5}` | 送信時にインポートしたCSV/Excelの任意列 |

差し込みCSV/Excelは「会員番号」列をキーとして members と突合する（「会員番号」列は必須）。  
列名マッピングは送信時のダイアログで設定し、`{col1}`〜`{col5}` に対応させる。  
突合できなかった行はスキップして警告表示する。

---

## 6. Microsoft Graph API 認証仕様

クライアントクレデンシャルフロー（アプリ認証）を使用する。

**設定項目（app_config.json に保存）：**
- テナントID（tenant_id）
- クライアントID（client_id）
- クライアントシークレット（client_secret）
- 送信元メールアドレス（from_address）
- テスト送信先アドレス（test_address）

**送信フロー：**
1. `https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token` にPOSTしてアクセストークンを取得
2. `https://graph.microsoft.com/v1.0/users/{from_address}/sendMail` にPOSTしてメール送信
3. 添付ファイルは `attachments` 配列にBase64エンコードして含める

**必要なAzure ADアプリ権限：**
- `Mail.Send`（アプリケーション権限）

---

## 7. 個別添付ファイルのマッチング仕様

- フォルダを指定し、ファイル名ルールを設定する（例：`{会員番号}.pdf`）
- ファイル名ルールで使用できるプレースホルダーは `{会員番号}` のみ
- ルールに従ってフォルダ内のファイルと各会員をマッチング
- 確認テーブルに以下を表示：

| 事業所名 | 会員番号 | 送信先アドレス | 対応ファイル名 | 存在確認 |
|---|---|---|---|---|
| ○○商事 | A-001 | info@example.com | A-001.pdf | ○ |
| △△産業 | A-002 | somu@example.com | A-002.pdf | × |

- 「×」の企業は警告表示し、「スキップして続行」または「中止」を選択できる

---

## 8. 共有フォルダ運用

- アプリ本体（Pythonスクリプト or exe）と `cci_mail.db` を同一の共有フォルダに配置
- `app_config.json`（Graph API認証情報を含む）も同フォルダに配置
- SQLiteの同時書き込み制限に対応するため、WALモード（Write-Ahead Logging）を有効化する
- 同時に複数人が送信操作を行うことは想定しない（送信中は「送信中」状態をUIで表示して抑制）
- 操作者は起動時または送信時にドロップダウンで職員名を選択する（パスワード認証なし）

---

## 9. 各タブの機能仕様

### 9.1 名簿管理タブ

- 会員一覧テーブル（会員番号・会議所役職・事業所名・氏名・メール件数）
- 追加・編集・削除ボタン（削除は確認ダイアログ必須）
- **編集ダイアログ（`member_edit_dialog.py`）：**
  - 全フィールド入力
  - メールアドレス最大5件（ラベル付き）
  - **変更理由入力欄**（保存時に必須）
  - **操作者選択ドロップダウン**
  - 保存時に変更前スナップショットを `member_history` に自動記録
- **変更履歴ボタン**：選択した会員の履歴一覧ダイアログを表示
  - 変更日時・変更者・変更理由・変更前データのJSON差分
- Excel/CSVインポートボタン：列マッピング画面を経由して一括登録
- キーワード検索・会議所役職フィルタ

### 9.2 テンプレートタブ

- テンプレート一覧（名前・件名・更新日）
- 追加・編集・削除
- 編集ダイアログ：件名・本文テキストエリア・デフォルト署名選択
- プレースホルダー一覧をサイドに常時表示

### 9.3 メール送信タブ

送信フローを1タブ内でステップ形式に展開する。

**Step 1：操作者選択**
- 職員ドロップダウンで操作者を選択（全ステップ共通で使用）

**Step 2：宛先選択**
- 「役職で選択」：会議所役職チェックボックス（複数可）
- 「企業で選択」：会員一覧チェックボックス（個別選択）
- 2つの選択方法は併用可能（和集合・重複は自動除外）
- 選択件数・選択中の企業名をリアルタイム表示

**Step 3：テンプレート・署名選択**
- ドロップダウンでテンプレート選択
- 件名・本文プレビュー（その場で一時編集可）
- 署名選択（テンプレートのデフォルト署名が自動セット）
- 本文末尾に署名が付加された状態でプレビュー

**Step 4：差し込みデータ（任意）**
- CSV/Excelインポートボタン
- 列名マッピングダイアログ：`{col1}`〜`{col5}` と列名を対応付け
- インポート後、各社のプレビューをテーブル表示（会員番号・col1〜col5の値）
- ファイルを読み込まない場合、`{col1}`〜`{col5}` は空文字で展開

**Step 5：添付ファイル（任意）**
- 「全社共通ファイル」：ファイル選択（複数ファイル可）
- 「会社別ファイル」：
  - フォルダ選択ボタン
  - ファイル名ルール入力（例：`{会員番号}.pdf`）
  - 「マッチング確認」ボタンで確認テーブルを表示
  - 見つからない企業は×表示＋警告カウント
  - スキップ or 中止を選択して次へ進む

**Step 6：最終確認・送信**
- 送信対象一覧テーブル（事業所名・送信先アドレス・添付ファイル・差し込みプレビュー）
- ジョブ名入力欄（送信履歴に保存される名称）
- テスト送信ボタン（自分のアドレスへサンプル1通）
- 「送信実行」ボタン：プログレスバーで進捗表示
- 送信完了後サマリー表示（成功N件・エラーN件・スキップN件）

### 9.4 送信履歴タブ

- ジョブ一覧（送信日・操作者・ジョブ名・対象件数・成功/エラー件数）
- ジョブ選択で明細テーブルを表示（事業所名・送信先・件名・ステータス・エラー内容）
- CSV出力ボタン

### 9.5 設定タブ

- **Microsoft 365設定：** テナントID・クライアントID・クライアントシークレット・送信元アドレス・テスト送信先
- 接続テストボタン（Graph APIへの認証確認）
- **署名管理：** 追加・編集・削除・デフォルト指定
- **会議所役職マスタ：** 追加・編集・削除・表示順並び替え
- **職員管理：** 追加・編集・有効/無効切り替え

---

## 10. セキュリティ考慮事項

- `app_config.json` にはクライアントシークレットが含まれるため、共有フォルダのアクセス権を職員のみに制限すること
- シークレットの画面表示はマスク（`****`）する
- ログに認証情報を出力しない

---

## 11. 外部ライブラリ

```
PyQt6
SQLAlchemy
openpyxl
requests          # Graph API HTTP通信
msal              # Microsoft Authentication Library（トークン取得）
```
