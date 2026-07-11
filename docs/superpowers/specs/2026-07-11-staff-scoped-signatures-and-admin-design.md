# 署名の担当者別管理と職員管理の管理者限定 設計書

**作成日：** 2026-07-11
**ステータス：** 承認済み

---

## 1. 概要

以下2点を実装する。

1. **署名の担当者スコープ化**：署名は作成した担当者本人のみが閲覧・編集・選択できるようにする（他の担当者の署名は見えない）。デフォルト署名も担当者ごとに独立して設定できる。**テンプレートは引き続き全担当者で共有**する（今回のスコープ化の対象外）。
2. **職員管理の管理者限定**：「職員管理」タブ（設定内）は管理者権限を持つ職員のみアクセスできるようにする。

認証はパスワードなしの信頼ベース（ログイン画面で自分の名前を選ぶだけ）のままとする。今回の変更は不正アクセス防止ではなく、誤操作防止と画面の整理が目的。

既存の署名データは変更作業前にユーザー自身が削除済みのため、データ移行（旧データの扱い）は考慮不要。ただし当該DBの職員「水谷」（既存id=1）を初期管理者に手動設定する一度限りのデータ更新を行う。

---

## 2. データモデルの変更

### 2.1 `Staff`に管理者フラグを追加

`app/database/models.py`:

```python
class Staff(Base):
    __tablename__ = "staff"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)

    send_jobs = relationship("SendJob", back_populates="staff")
```

### 2.2 `Signature`に担当者参照を追加

```python
class Signature(Base):
    __tablename__ = "signatures"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    body = Column(Text, nullable=False)
    is_default = Column(Boolean, default=False)
    staff_id = Column(Integer, ForeignKey("staff.id"), nullable=True)

    templates = relationship("EmailTemplate", back_populates="signature")
```

`staff_id`は`nullable=True`とする（既存テーブルへのALTER TABLE追加のため。将来的に所有者なしの行が生じても、サービス層では常に`staff_id`で絞り込むため、そのような行は誰からも見えなくなる——今回は既存データを削除済みのため実質発生しない）。ORMの逆参照（`Staff.signatures`）は現状どこからも使わないため追加しない（YAGNI）。

### 2.3 マイグレーション

`app/database/connection.py`の`_migrate_sqlite` / `_migrate_postgresql`に、既存パターンと同様のALTER TABLE処理を追加する。

- `staff`テーブルに`is_admin`カラムが無ければ追加（デフォルト値は`0`/`False`相当）
- `signatures`テーブルに`staff_id`カラムが無ければ追加

### 2.4 一度限りのデータ更新（このDBのみ）

スキーマ移行後、現在の職員「水谷」（既存id=1）の`is_admin`を`True`に更新するワンショットスクリプトを実行する（自動マイグレーションには含めない——特定の名前を全デプロイ環境で自動的に管理者化するのは誤り）。

---

## 3. サービス層の変更

### 3.1 `app/services/staff_service.py`

```python
def create_staff(session: Session, name: str, is_admin: bool = False) -> Staff:
    s = Staff(name=name, is_active=True, is_admin=is_admin)
    session.add(s)
    session.commit()
    return s


def set_admin(session: Session, staff_id: int, is_admin: bool) -> None:
    s = session.get(Staff, staff_id)
    if s:
        s.is_admin = is_admin
        session.commit()
```

（`get_active_staff` / `get_all_staff` / `get_staff_by_name` / `set_active`は変更なし）

### 3.2 `app/services/signature_service.py`

全関数を担当者スコープに変更する。

```python
def create_signature(session: Session, name: str, body: str, staff_id: int,
                     is_default: bool = False) -> Signature:
    sig = Signature(name=name, body=body, staff_id=staff_id, is_default=is_default)
    session.add(sig)
    session.commit()
    return sig


def get_signatures(session: Session, staff_id: int) -> list[Signature]:
    return (session.query(Signature)
            .filter_by(staff_id=staff_id)
            .order_by(Signature.name).all())


def get_default_signature(session: Session, staff_id: int) -> Signature | None:
    return (session.query(Signature)
            .filter_by(staff_id=staff_id, is_default=True).first())


def set_default(session: Session, sig_id: int, staff_id: int) -> None:
    session.query(Signature).filter_by(staff_id=staff_id).update({"is_default": False})
    sig = session.get(Signature, sig_id)
    if sig:
        sig.is_default = True
    session.commit()


def update_signature(session: Session, sig_id: int, **kwargs) -> Signature:
    # 変更なし（呼び出し元は自分の署名のIDしか渡さない前提）

def delete_signature(session: Session, sig_id: int) -> None:
    # 変更なし
```

`set_default`は「自分の署名の中でのみ」`is_default`をクリアする（他の担当者のデフォルト署名には影響しない）。

---

## 4. UI変更

### 4.1 ログインダイアログ：初回登録者を自動的に管理者にする

`app/ui/dialogs/login_dialog.py`の`_add_staff`（職員が0人の時のみ表示されるボタン）を変更する。

```python
    def _add_staff(self):
        name, ok = QInputDialog.getText(self, "職員を追加", "職員名を入力してください：")
        if not ok or not name.strip():
            return
        session = get_session()
        try:
            create_staff(session, name.strip(), is_admin=True)
        finally:
            session.close()
        self._load_staff()
        QMessageBox.information(
            self, "登録完了",
            f"「{name.strip()}」を管理者として登録しました。")
```

これにより「職員が誰もいない状態」から最初に登録した人が自動的に管理者になり、以降の職員追加（管理者限定の職員管理タブ）に詰まらない。

### 4.2 `SettingsTab` / `TemplateTab` / `SendTab` に担当者情報を渡す

`app/ui/main_window.py`の`_build_tabs`を変更する。

```python
            tabs.addTab(SendTab(staff_name=self._staff_name), "メール送信")
            tabs.addTab(TemplateTab(staff_name=self._staff_name), "テンプレート")
            tabs.addTab(SettingsTab(staff_name=self._staff_name), "設定")
```

### 4.3 `SettingsTab`：職員管理タブを管理者限定に

```python
class SettingsTab(QWidget):
    def __init__(self, staff_name: str = ""):
        super().__init__()
        session = get_session()
        try:
            staff = get_staff_by_name(session, staff_name) if staff_name else None
        finally:
            session.close()
        self._staff_id = staff.id if staff else None
        is_admin = bool(staff and staff.is_admin)

        layout = QVBoxLayout(self)
        inner = QTabWidget()
        inner.setMaximumWidth(900)
        inner.addTab(_GraphSettingsWidget(), "Microsoft 365")
        inner.addTab(_SignatureWidget(self._staff_id), "署名管理")
        inner.addTab(_CommitteeWidget(), "委員会管理")
        if is_admin:
            inner.addTab(_StaffWidget(), "職員管理")
        inner.addTab(_DbSettingsWidget(), "データベース接続")
        inner.addTab(_ExportSettingsWidget(), "出力設定")
        if os.environ.get("CCI_MAIL_DEV_TOOLS") == "1":
            inner.addTab(_DataWidget(), "データ管理")
        layout.addWidget(inner)
```

`staff_name`未指定（空文字、既存テストの後方互換）の場合は`staff_id=None`・`is_admin=False`となり、職員管理タブは表示されない（安全側デフォルト）。

### 4.4 `_SignatureWidget`：担当者スコープの署名一覧

```python
class _SignatureWidget(QWidget):
    def __init__(self, staff_id: int | None):
        super().__init__()
        self._staff_id = staff_id
        ...  # 既存のUI構築はそのまま

    def _load(self):
        session = get_session()
        try:
            self._signatures = get_signatures(session, self._staff_id) if self._staff_id else []
        finally:
            session.close()
        ...

    def _add(self):
        ...
        if self._staff_id is None:
            QMessageBox.warning(self, "エラー", "担当者情報が取得できないため署名を保存できません。")
            return
        session = get_session()
        create_signature(session, name, body, self._staff_id)
        ...

    def _update(self):
        # update_signatureは変更なし（sig_idのみで一意に更新）

    def _set_default(self):
        ...
        set_default(session, sig_id, self._staff_id)
```

### 4.5 `_StaffWidget`：管理者フラグの表示・切替を追加

- テーブルを3列に変更：`["職員名", "有効", "管理者"]`
- 「追加」フォームに「管理者にする」チェックボックスを追加し、`create_staff(session, name, is_admin=checked)`で渡す
- 「管理者権限 切替」ボタンを追加。選択中の職員の`is_admin`を反転する。ただし**管理者が自分1人だけの状態でその1人を非管理者にしようとした場合は確認ダイアログを出し、実行すると職員管理タブに誰もアクセスできなくなる旨を警告する**（既定ボタンNo）。

### 4.6 `SendTab` / `TemplateTab`：署名コンボを担当者スコープに

`app/ui/send_tab.py`・`app/ui/template_tab.py`の`_load_combos` / `_load`内、`get_signatures(session)` → `get_signatures(session, staff_id)`に変更する。`staff_id`は`self._staff_name`から`get_staff_by_name`で解決する（`SendTab`は既に`_execute_send`内で同じ解決パターンを使用済み）。

`TemplateTab.__init__`に`staff_name: str = ""`を追加する（現在は引数なし）。

テンプレート自体（`EmailTemplate`）・件名・本文は今まで通り全担当者で共有する。テンプレートが参照する`signature_id`が、閲覧中の担当者から見えない（他人の）署名を指している場合、署名コンボは一致する項目が見つからず「（なし）」のまま表示される（データは失われないが、そのテンプレートを開いた担当者は自分の署名を選び直す必要がある）。この挙動はスコープ内の妥当な副作用として許容する。

---

## 5. テスト方針

既存パターン（pytest + pytest-qt、`db_session`フィクスチャ、UI系は`monkeypatch`でサービス関数を差し替え）に従う。

- `tests/test_staff_service.py`：`create_staff`の`is_admin`引数、新規`set_admin`
- `tests/test_signature_service.py`：全関数呼び出しに`staff_id`引数を追加。担当者Aの署名が担当者Bの`get_signatures`に含まれないこと、`set_default`が担当者を跨いで影響しないことを検証するテストを追加
- `tests/test_settings_tab_staff_admin.py`（新規）：管理者でログイン時は職員管理タブが表示され、非管理者・未ログイン（staff_name未指定）では非表示になることを検証（`test_data_widget_hidden.py`の開発者フラグテストと同じパターン）
- `tests/test_signature_widget_scoped.py`（新規）：`_SignatureWidget`が指定された`staff_id`の署名のみ表示すること
- `tests/test_login_dialog_first_staff_admin.py`（新規）：職員0人の状態から`_add_staff`で登録した職員が`is_admin=True`になることを検証
- 既存の`tests/test_signature_widget_textedit.py`・`tests/test_data_widget_hidden.py`・`send_tab`/`template_tab`関連の既存テストは、新しい引数（`staff_id`／`staff_name`）に合わせて更新する

---

## 6. スコープ外

- パスワード等の本格的な認証機構の導入（信頼ベースのまま）
- テンプレートの担当者スコープ化（今回は明示的に対象外、共有のまま）
- 署名の「共有」機能（特定の署名を他担当者にも見せる、等のオプトイン共有は今回実装しない）
- 管理者以外のロール区分（一般職員／管理者の2段階のみ。閲覧専用ログインは既存のまま変更なし）
