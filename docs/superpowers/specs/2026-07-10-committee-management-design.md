# 委員会管理・委員会別メール送信 設計書

**作成日：** 2026-07-10
**ステータス：** 承認済み

---

## 1. 概要

会員（事業所）は「総務・運営委員会」「地域経済推進委員会」「中小・小規模企業委員会」の3委員会のうち最大1つに所属する（未所属もあり得る）。委員会は既存の「会議所役職（Position）」とは独立した属性として管理し、以下を実現する。

- 委員会マスタの管理（設定タブでの追加・編集・削除）
- 会員ごとの委員会の設定（会員編集ダイアログ）
- 名簿一覧での委員会表示
- 委員会ごとに絞り込んでメール送信（送信タブ）
- 名簿インポート/エクスポートでの委員会列対応

既存の`Position`（会議所役職）の実装パターンを踏襲する。サービス層・DBスキーマの変更は本機能に必要な範囲に限定する。

---

## 2. データモデル

### 2.1 新規テーブル `Committee`

`app/database/models.py`に追加。`Position`と同型。

```python
class Committee(Base):
    __tablename__ = "committees"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    sort_order = Column(Integer, nullable=False, default=0)

    members = relationship("Member", back_populates="committee")
```

### 2.2 `Member`テーブルの変更

`committee_id`（FK, nullable）を追加。

```python
committee_id = Column(Integer, ForeignKey("committees.id"), nullable=True)
committee = relationship("Committee", back_populates="members")
```

### 2.3 マイグレーション

`Committee`テーブルは`Base.metadata.create_all()`で自動生成される。既存`members`テーブルへの`committee_id`カラム追加は、`app/database/connection.py`の`_migrate_sqlite` / `_migrate_postgresql`に既存パターンと同様のALTER TABLE処理を追加する。

---

## 3. サービス層

`app/services/committee_service.py`（新規、`position_service.py`と同型）:

```python
def create_committee(session: Session, name: str, sort_order: int) -> Committee
def get_committees(session: Session) -> list[Committee]
def update_committee(session: Session, committee_id: int, **kwargs) -> Committee
def delete_committee(session: Session, committee_id: int) -> None
```

`delete_committee`は、削除対象の委員会に所属する会員がいれば呼び出し側（UI）で確認・`committee_id`をNULLに戻す処理を行う前提とする（`Position`削除に確認ダイアログの前例がないため、UI側で件数を表示して警告する）。

---

## 4. UI変更

### 4.1 設定タブ：委員会管理（新規 `_CommitteeWidget`）

`app/ui/settings_tab.py`に`_SignatureWidget`と同じ構成のウィジェットを追加し、`SettingsTab.__init__`で新規タブ「委員会管理」として登録する。

- 一覧テーブル（委員会名の1列）
- 名前入力欄＋「追加」「更新」「削除」ボタン
- 並び替えUIは作らない（3件程度のため、追加順の`sort_order`自動採番で十分と判断）
- 「削除」時、所属会員が1件以上いる場合は件数を示して確認ダイアログを表示（`QMessageBox.question`、既定ボタンNo）。承認されたら該当会員の`committee_id`をNULLにしてから委員会を削除する。

### 4.2 会員編集ダイアログ（`member_edit_dialog.py`）

- 「会議所役職」行の下に「委員会」行を追加。コンボボックスは既存の`_NoWheelComboBox`を再利用（スクロール誤操作防止）。
- 選択肢は「（なし）」＋委員会一覧（`sort_order`順）。
- `_current_state()` / 未保存変更検知タプルに`committee_id`を含める。

### 4.3 名簿タブ（`member_tab.py`）

- 一覧テーブルに「委員会」列を追加（「会議所役職」列の右隣）。列数は10→11に変更。
- 議員退任者のグレー表示ロジックを他列と同様に適用する。

### 4.4 送信タブ（`send_tab.py`）

Step 1「宛先条件」に3つ目のモード「委員会で選ぶ」を追加する。

- `QRadioButton`を3択に変更（`_rb_by_pos` / `_rb_by_attend` / `_rb_by_committee`）
- 委員会一覧を`QListWidget`（複数選択可・Ctrl+クリック、`_pos_list`と同じUIパターン）で表示する`_committee_panel`を新設
- 選択された委員会に所属する会員（`member.committee_id in selected_committee_ids`）を宛先チェックに反映する`_on_committee_select`を追加
- `_on_mode_change`で3パネルの表示切り替えを行う

### 4.5 インポート/エクスポート

- `import_service.py`：`position_name`列マッピングと同じパターンで`committee_name`列を追加。未知の委員会名が来た場合は新規`Committee`を自動作成する（`Position`と同じ挙動）。
- `app/ui/dialogs/import_dialog.py`の列マッピング対象（`_MEMBER_FIELDS`相当）に「委員会」を追加。
- `export_service.py`のExcel/CSV出力列に「委員会」を追加（会議所役職列の隣）。

---

## 5. テスト方針

既存パターン（pytest + pytest-qt、`db_session`フィクスチャ、UI系は`monkeypatch`でサービス関数を差し替え）に従う。

- `tests/test_committee_service.py`（新規）：create/get/update/delete
- `tests/test_import_committee.py`（新規）：`committee_name`列からの新規作成・既存マッピング
- `tests/test_export_committee.py`（新規）：出力列に委員会名が含まれること
- `tests/test_member_tab_committee_column.py`（新規）：委員会列の表示
- `tests/test_send_tab_committee_filter.py`（新規）：委員会選択で宛先が正しく絞り込まれること
- `tests/test_member_edit_dialog_committee.py`（新規）：委員会コンボの保存・未保存検知への組み込み

---

## 6. スコープ外

- 会員が複数委員会に同時所属するケース（今回は最大1委員会という前提）
- 委員会マスタの並び替えUI（3件程度のため見送り、必要になれば`OrderSettingsDialog`拡張で対応）
- 委員会専用のメールテンプレート自動選択（送信タブでの絞り込みのみ対応、テンプレートは引き続き手動選択）
