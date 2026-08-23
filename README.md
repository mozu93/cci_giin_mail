# cci-mail — 商工会議所メール配信システム

商工会議所が会員企業（議員等）に対してメールを一斉配信するためのデスクトップアプリケーション（Windows / PyQt6）。
名簿管理、委員会管理、会議（出欠受付）管理、テンプレート・署名管理、Microsoft Graph API 経由のメール送信、送信履歴管理を備え、複数職員での共同利用（SQLite単独運用 / PostgreSQLによる複数台共有運用）に対応する。

## 主な機能

- **名簿管理**：会員情報（会員番号・事業所名・役職・委員会・氏名・フリガナ・メール最大5件・顔写真）の登録・編集・削除、Excel/CSVインポート・エクスポート、変更履歴の記録・閲覧。フリガナはひらがな・全角／半角カタカナのいずれでも検索可能
- **委員会管理**：委員会の追加・編集・削除、会員ごとの委員会割り当て
- **会議管理（受付）**：会議の作成、事前入力（出席・代理・委任・欠席）、当日受付、議決権数・議事録用氏名の生成、受付ログ、A4縦向きExcel/CSV出力
- **メール送信**：Microsoft Graph API（Entraアプリ登録）による認証付き送信、CC/BCC、全件を安全な宛先へ振り替えるテストモード、認証アカウント・重複宛先の安全確認、役職/委員会/会議出欠による宛先絞り込み、タブ移動後も保持される宛先・条件選択、差し込みデータ（`{事業所名}` `{氏名}` `{col1}`〜`{col5}` 等）、共通・個別添付ファイル、履歴付きテスト送信
- **テンプレート・署名管理**：担当者スコープの署名、差し込みタグ対応テンプレート
- **送信履歴**：送信ジョブ・ログの記録・閲覧、CSV出力、一定期間経過後の自動削除、Exchange Onlineのメッセージ追跡結果による配信状況確認（配信済み・配信失敗・隔離・スパム処理など）
- **自動更新**：起動時・30分ごとの新バージョン確認、ヘルプメニューからの手動確認、接続エラー表示、SHA-256検証付きインストーラーダウンロード

詳細な仕様は [`docs/superpowers/specs/`](docs/superpowers/specs/) 配下の設計書を参照。

## 技術スタック

| 要素 | 採用技術 |
|---|---|
| 言語 | Python 3.11+ |
| UI | PyQt6 |
| データベース | SQLAlchemy（SQLite / PostgreSQL） |
| メール送信 | Microsoft Graph API（OAuth2 委任認証、msal） |
| インポート/エクスポート | openpyxl |
| パッケージング | PyInstaller（`cci_mail.spec`） |

## セットアップ（開発環境）

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

## 実行

```bash
python main.py
```

または Windows では `start.bat` をダブルクリックする。

初回起動時はセットアップウィザードが表示され、データベース接続（SQLite / PostgreSQL）や Microsoft Graph API の接続情報（`app_config.json`）を設定する。

## テスト

```bash
pytest
```

`pytest.ini` により `tests/` 配下の `test_*.py` が対象（PyQt6 UIテストを含むため `pytest-qt` を使用）。
テスト時の設定・データ・認証キャッシュは一時ディレクトリへ隔離され、利用者の実データを変更しない。

## ビルド（配布用exe作成）

```bash
pyinstaller cci_mail.spec
```

`dist/CCIMail/` に実行ファイル一式が生成される。

## ディレクトリ構成

```
main.py                   # エントリーポイント
app/
  database/               # SQLAlchemy モデル・接続管理
  services/                # 業務ロジック（名簿・委員会・会議・メール送信・テンプレート等）
  ui/                      # PyQt6 画面（各タブ・ダイアログ）
  utils/                   # 設定読み書き・アップデート・エラー整形等
tests/                     # pytest テスト
docs/                      # 設計書・ユーザー/管理者マニュアル・運用手順書
```

## ドキュメント

- [ユーザーマニュアル](docs/ユーザーマニュアル.md)
- [管理者マニュアル](docs/管理者マニュアル.md)
- [サーバーPC変更手順](docs/サーバーPC変更手順.md)
- [リリースノート](RELEASE_NOTES.md)
