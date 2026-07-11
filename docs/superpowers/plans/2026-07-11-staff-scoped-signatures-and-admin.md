# 署名の担当者別管理と職員管理の管理者限定 実装計画

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `docs/superpowers/specs/2026-07-11-staff-scoped-signatures-and-admin-design.md` に基づき、署名を担当者ごとにスコープ化し、職員管理タブを管理者限定にする。

**Architecture:** `Staff`に`is_admin`、`Signature`に`staff_id`を追加。サービス層（`signature_service.py`）を担当者スコープのクエリに変更し、`staff_service.py`に管理者関連関数を追加。UI層（`settings_tab.py`, `send_tab.py`, `template_tab.py`, `login_dialog.py`, `main_window.py`）にログイン中の担当者情報を配線する。テンプレート（`EmailTemplate`）はスコープ化しない（共有のまま）。

**Tech Stack:** Python 3.11+, PyQt6, SQLAlchemy, pytest, pytest-qt

## Global Constraints

- 認証はパスワードなしの信頼ベースのまま変更しない（ログイン画面で名前を選ぶだけ）。
- テンプレート（`EmailTemplate`）は担当者スコープ化の対象外。全担当者で共有したままにする。
- 既存の命名規則・実装パターン（`get_session()`の都度生成、`QMessageBox`の既定ボタンNo、`os.environ.get("CCI_MAIL_DEV_TOOLS") == "1"`による開発者フラグと同じ「条件付きタブ追加」パターン）を踏襲する。
- `Staff`/`Signature`テーブルへのカラム追加は、`app/database/connection.py`の`_migrate_sqlite` / `_migrate_postgresql`に既存パターン（`committee_id`追加等）と同様のALTER TABLE処理を追加する。
- サービス層の関数シグネチャ変更（`staff_id`引数の追加）は、呼び出し元をすべて追随させる。
- `staff_name`が空文字または該当する`Staff`が見つからない場合は、常に「安全側」（管理者なし・署名なし）にフォールバックする。
- 各タスクは独立してテスト・コミット可能。Task番号順に依存関係があるため、番号順に実施する。
- テストは pytest-qt の `qtbot` フィクスチャを使う。実DB（`get_session()`）へのアクセスが発生する箇所は `monkeypatch` でサービス関数を差し替える（`tests/test_main_window.py`・`tests/test_main_window_staff_wiring.py`は既存の慣例に倣い実DBへの依存を許容する）。

---

## タスク一覧

| # | 内容 | 対象ファイル |
|---|---|---|
| 1 | `Staff.is_admin` / `Signature.staff_id` の追加とマイグレーション | models.py, connection.py |
| 2 | `staff_service.py`に管理者関連関数を追加 | staff_service.py |
| 3 | `signature_service.py`を担当者スコープに変更 | signature_service.py |
| 4 | ログインダイアログ：初回登録者を自動的に管理者にする | login_dialog.py |
| 5 | `SettingsTab`/`_SignatureWidget`の担当者スコープ・管理者限定表示 | settings_tab.py |
| 6 | `_StaffWidget`の管理者列・切替ボタン追加 | settings_tab.py |
| 7 | `SendTab`の署名コンボを担当者スコープに | send_tab.py |
| 8 | `TemplateTab`の署名コンボを担当者スコープに | template_tab.py |
| 9 | `main_window.py`の配線更新 | main_window.py |

---

## Task 1: `Staff.is_admin` / `Signature.staff_id` の追加とマイグレーション

**Files:**
- Modify: `app/database/models.py`（`Staff`, `Signature`クラス定義）
- Modify: `app/database/connection.py`（`_migrate_sqlite`, `_migrate_postgresql`）
- Test: `tests/test_migration_staff_admin_signature_owner.py`（新規）

**Interfaces:**
- Produces: `Staff.is_admin`（`Boolean`, デフォルト`False`）, `Signature.staff_id`（`Integer`, `ForeignKey("staff.id")`, `nullable=True`）

- [ ] **Step 1: 失敗するテストを書く**

```python
# tests/test_migration_staff_admin_signature_owner.py
import sqlite3
from sqlalchemy import create_engine, text
from app.database.connection import _migrate_sqlite


def test_migrate_sqlite_adds_is_admin_and_staff_id_columns(tmp_path):
    db_path = tmp_path / "old_schema.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "CREATE TABLE staff (id INTEGER PRIMARY KEY, name TEXT NOT NULL, "
        "is_active BOOLEAN)")
    conn.execute(
        "CREATE TABLE signatures (id INTEGER PRIMARY KEY, name TEXT NOT NULL, "
        "body TEXT NOT NULL, is_default BOOLEAN)")
    conn.commit()
    conn.close()

    engine = create_engine(f"sqlite:///{db_path}")
    _migrate_sqlite(engine)

    with engine.connect() as conn:
        staff_cols = {row[1] for row in conn.execute(text("PRAGMA table_info(staff)"))}
        sig_cols = {row[1] for row in conn.execute(text("PRAGMA table_info(signatures)"))}
    assert "is_admin" in staff_cols
    assert "staff_id" in sig_cols


def test_migrate_sqlite_is_idempotent(tmp_path):
    db_path = tmp_path / "old_schema2.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "CREATE TABLE staff (id INTEGER PRIMARY KEY, name TEXT NOT NULL, "
        "is_active BOOLEAN)")
    conn.execute(
        "CREATE TABLE signatures (id INTEGER PRIMARY KEY, name TEXT NOT NULL, "
        "body TEXT NOT NULL, is_default BOOLEAN)")
    conn.commit()
    conn.close()

    engine = create_engine(f"sqlite:///{db_path}")
    _migrate_sqlite(engine)
    _migrate_sqlite(engine)  # 2回目もエラーにならないこと
```

- [ ] **Step 2: テストを実行して失敗を確認**

Run: `pytest tests/test_migration_staff_admin_signature_owner.py -v`
Expected: FAIL — `assert "is_admin" in staff_cols`（現状は`staff`テーブルに`is_admin`列がないため）

- [ ] **Step 3: モデルとマイグレーションを実装**

`app/database/models.py`の`Signature`クラス定義を以下に置き換える:

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

`app/database/models.py`の`Staff`クラス定義を以下に置き換える:

```python
class Staff(Base):
    __tablename__ = "staff"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)

    send_jobs = relationship("SendJob", back_populates="staff")
```

`app/database/connection.py`の`_migrate_sqlite`関数の末尾（`members_cols`の`committee_id`追加ブロックの直後、関数の最後）に以下を追加する:

```python
        staff_cols = {
            row[1] for row in conn.execute(text("PRAGMA table_info(staff)"))
        }
        if "is_admin" not in staff_cols:
            conn.execute(text(
                "ALTER TABLE staff ADD COLUMN is_admin BOOLEAN DEFAULT 0"
            ))
            conn.commit()

        signatures_cols = {
            row[1] for row in conn.execute(text("PRAGMA table_info(signatures)"))
        }
        if "staff_id" not in signatures_cols:
            conn.execute(text(
                "ALTER TABLE signatures ADD COLUMN staff_id INTEGER"
            ))
            conn.commit()
```

`app/database/connection.py`の`_migrate_postgresql`関数の末尾（`committee_id`追加ブロックの直後）に以下を追加する:

```python
        staff_cols = {col["name"] for col in insp.get_columns("staff")}
        if "is_admin" not in staff_cols:
            conn.execute(text("ALTER TABLE staff ADD COLUMN is_admin BOOLEAN DEFAULT FALSE"))

        signatures_cols = {col["name"] for col in insp.get_columns("signatures")}
        if "staff_id" not in signatures_cols:
            conn.execute(text("ALTER TABLE signatures ADD COLUMN staff_id INTEGER"))
```

（`_migrate_postgresql`は`insp.get_columns("members")`を使う既存パターンに倣い、`staff`・`signatures`テーブル用にも同じ`insp`インスタンスを再利用する。）

- [ ] **Step 4: テストを実行して成功を確認**

Run: `pytest tests/test_migration_staff_admin_signature_owner.py -v`
Expected: PASS

- [ ] **Step 5: コミット**

```bash
git add app/database/models.py app/database/connection.py tests/test_migration_staff_admin_signature_owner.py
git commit -m "feat: Staffに管理者フラグ、Signatureに担当者参照を追加"
```

---

## Task 2: `staff_service.py`に管理者関連関数を追加

**Files:**
- Modify: `app/services/staff_service.py`
- Test: `tests/test_staff_service.py`（既存ファイルに追加）

**Interfaces:**
- Consumes: `Staff.is_admin`（Task 1）
- Produces: `create_staff(session, name, is_admin=False) -> Staff`（既存関数にキーワード引数追加）, `set_admin(session, staff_id, is_admin) -> None`（新規）

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_staff_service.py`の末尾に以下を追加する（既存のimport文に`set_admin`を追加）:

```python
from app.services.staff_service import (
    create_staff, get_active_staff, get_all_staff,
    get_staff_by_name, set_active, set_admin,
)


def test_create_staff_defaults_to_non_admin(db_session):
    s = create_staff(db_session, "山田")
    assert s.is_admin is False


def test_create_staff_with_admin_flag(db_session):
    s = create_staff(db_session, "水谷", is_admin=True)
    assert s.is_admin is True


def test_set_admin_toggles_flag(db_session):
    s = create_staff(db_session, "山田")
    set_admin(db_session, s.id, True)
    db_session.refresh(s)
    assert s.is_admin is True
    set_admin(db_session, s.id, False)
    db_session.refresh(s)
    assert s.is_admin is False
```

既存のimport文（ファイル冒頭）が`from app.services.staff_service import create_staff, ...`のような形の場合は、上記のimport文で置き換える。

- [ ] **Step 2: テストを実行して失敗を確認**

Run: `pytest tests/test_staff_service.py -v`
Expected: FAIL — `ImportError: cannot import name 'set_admin'`

- [ ] **Step 3: `staff_service.py`を実装**

`app/services/staff_service.py`の`create_staff`関数を以下に置き換える:

```python
def create_staff(session: Session, name: str, is_admin: bool = False) -> Staff:
    s = Staff(name=name, is_active=True, is_admin=is_admin)
    session.add(s)
    session.commit()
    return s
```

`set_active`関数の直後に`set_admin`関数を追加する:

```python
def set_admin(session: Session, staff_id: int, is_admin: bool) -> None:
    s = session.get(Staff, staff_id)
    if s:
        s.is_admin = is_admin
        session.commit()
```

- [ ] **Step 4: テストを実行して成功を確認**

Run: `pytest tests/test_staff_service.py -v`
Expected: PASS

- [ ] **Step 5: コミット**

```bash
git add app/services/staff_service.py tests/test_staff_service.py
git commit -m "feat: staff_serviceに管理者フラグの作成・切替を追加"
```

---

## Task 3: `signature_service.py`を担当者スコープに変更

**Files:**
- Modify: `app/services/signature_service.py`
- Test: `tests/test_signature_service.py`（既存ファイルを全面的に書き換え）

**Interfaces:**
- Consumes: `Signature.staff_id`（Task 1）
- Produces: `create_signature(session, name, body, staff_id, is_default=False) -> Signature`, `get_signatures(session, staff_id) -> list[Signature]`, `get_default_signature(session, staff_id) -> Signature | None`, `set_default(session, sig_id, staff_id) -> None`（いずれも`staff_id`引数を新規追加、既存呼び出し元は全てTask 5・7・8で追随させる）

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_signature_service.py`を以下の内容で全面的に置き換える:

```python
from app.services.signature_service import (
    create_signature, update_signature, delete_signature,
    get_signatures, get_default_signature, set_default
)
from app.services.staff_service import create_staff


def test_create_signature_requires_staff_id(db_session):
    staff = create_staff(db_session, "水谷")
    sig = create_signature(db_session, "標準署名", "商工会議所", staff.id)
    assert sig.id is not None
    assert sig.staff_id == staff.id
    assert not sig.is_default


def test_get_signatures_only_returns_own_staff(db_session):
    staff_a = create_staff(db_session, "水谷")
    staff_b = create_staff(db_session, "山田")
    create_signature(db_session, "水谷の署名", "本文A", staff_a.id)
    create_signature(db_session, "山田の署名", "本文B", staff_b.id)

    result = get_signatures(db_session, staff_a.id)
    assert [s.name for s in result] == ["水谷の署名"]


def test_set_default_clears_others_within_same_staff_only(db_session):
    staff_a = create_staff(db_session, "水谷")
    staff_b = create_staff(db_session, "山田")
    sig1 = create_signature(db_session, "署名A", "本文A", staff_a.id, is_default=True)
    sig2 = create_signature(db_session, "署名B", "本文B", staff_a.id)
    sig_other = create_signature(db_session, "署名C", "本文C", staff_b.id, is_default=True)

    set_default(db_session, sig2.id, staff_a.id)

    default_a = get_default_signature(db_session, staff_a.id)
    assert default_a.id == sig2.id
    db_session.refresh(sig1)
    assert not sig1.is_default

    db_session.refresh(sig_other)
    assert sig_other.is_default, "他の担当者のデフォルトには影響しないこと"


def test_get_default_returns_none_when_no_default(db_session):
    staff = create_staff(db_session, "水谷")
    create_signature(db_session, "署名A", "本文A", staff.id)
    assert get_default_signature(db_session, staff.id) is None
```

- [ ] **Step 2: テストを実行して失敗を確認**

Run: `pytest tests/test_signature_service.py -v`
Expected: FAIL — `TypeError: create_signature() missing 1 required positional argument: 'staff_id'`

- [ ] **Step 3: `signature_service.py`を実装**

`app/services/signature_service.py`全体を以下に置き換える:

```python
from sqlalchemy.orm import Session
from app.database.models import Signature


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
    sig = session.get(Signature, sig_id)
    if sig is None:
        raise ValueError(f"署名ID {sig_id} が見つかりません")
    for k, v in kwargs.items():
        setattr(sig, k, v)
    session.commit()
    return sig


def delete_signature(session: Session, sig_id: int) -> None:
    sig = session.get(Signature, sig_id)
    if sig:
        session.delete(sig)
        session.commit()
```

- [ ] **Step 4: テストを実行して成功を確認**

Run: `pytest tests/test_signature_service.py -v`
Expected: PASS

- [ ] **Step 5: コミット**

```bash
git add app/services/signature_service.py tests/test_signature_service.py
git commit -m "feat: signature_serviceを担当者スコープに変更"
```

---

## Task 4: ログインダイアログ：初回登録者を自動的に管理者にする

**Files:**
- Modify: `app/ui/dialogs/login_dialog.py`（`_add_staff`メソッド）
- Test: `tests/test_login_dialog_first_staff_admin.py`（新規）

**Interfaces:**
- Consumes: `create_staff(session, name, is_admin=False)`（Task 2）

- [ ] **Step 1: 失敗するテストを書く**

```python
# tests/test_login_dialog_first_staff_admin.py
class _FakeSession:
    def close(self):
        pass


def test_first_staff_added_from_login_becomes_admin(qtbot, monkeypatch):
    monkeypatch.setattr(
        "app.ui.dialogs.login_dialog.get_session", lambda: _FakeSession())
    monkeypatch.setattr(
        "app.ui.dialogs.login_dialog.get_all_staff", lambda s: [])
    monkeypatch.setattr(
        "app.ui.dialogs.login_dialog.get_last_staff", lambda: "")

    created = {}

    def fake_create_staff(session, name, is_admin=False):
        created["args"] = (name, is_admin)

    monkeypatch.setattr(
        "app.ui.dialogs.login_dialog.create_staff", fake_create_staff)

    from PyQt6.QtWidgets import QInputDialog, QMessageBox
    monkeypatch.setattr(QInputDialog, "getText",
                        staticmethod(lambda *a, **k: ("新人担当者", True)))
    monkeypatch.setattr(QMessageBox, "information",
                        staticmethod(lambda *a, **k: None))

    from app.ui.dialogs.login_dialog import LoginDialog
    dlg = LoginDialog()
    qtbot.addWidget(dlg)

    dlg._add_staff()

    assert created["args"] == ("新人担当者", True)
```

- [ ] **Step 2: テストを実行して失敗を確認**

Run: `pytest tests/test_login_dialog_first_staff_admin.py -v`
Expected: FAIL — `assert ('新人担当者', False) == ('新人担当者', True)`（現状は`is_admin`を指定していないためデフォルトの`False`になる）

- [ ] **Step 3: `_add_staff`を実装**

`app/ui/dialogs/login_dialog.py`の`_add_staff`メソッドを以下に置き換える:

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

- [ ] **Step 4: テストを実行して成功を確認**

Run: `pytest tests/test_login_dialog_first_staff_admin.py -v`
Expected: PASS

- [ ] **Step 5: コミット**

```bash
git add app/ui/dialogs/login_dialog.py tests/test_login_dialog_first_staff_admin.py
git commit -m "feat: 初回起動時にログイン画面から登録した職員を自動的に管理者にする"
```

---

## Task 5: `SettingsTab`/`_SignatureWidget`の担当者スコープ・管理者限定表示

**Files:**
- Modify: `app/ui/settings_tab.py`（import、`SettingsTab.__init__`、`_SignatureWidget`）
- Modify: `tests/test_signature_widget_textedit.py`（既存テストの引数更新）
- Modify: `tests/test_data_widget_hidden.py`（変更不要な場合は無変更で可、後述の回帰確認のみ）
- Test: `tests/test_settings_tab_staff_admin.py`（新規）
- Test: `tests/test_signature_widget_scoped.py`（新規）

**Interfaces:**
- Consumes: `get_staff_by_name(session, name)`（既存、`staff_service.py`）, `get_signatures(session, staff_id)` / `create_signature(session, name, body, staff_id)` / `set_default(session, sig_id, staff_id)`（Task 3）
- Produces: `SettingsTab.__init__(self, staff_name: str = "")`, `SettingsTab._staff_name`, `_SignatureWidget.__init__(self, staff_id: int | None)`

- [ ] **Step 1: 失敗するテストを書く**

```python
# tests/test_settings_tab_staff_admin.py
from PyQt6.QtWidgets import QTabWidget


class _FakeSession:
    def close(self):
        pass


class _Staff:
    def __init__(self, id, name, is_admin):
        self.id = id
        self.name = name
        self.is_admin = is_admin


def _patch_common(monkeypatch, staff_lookup=None):
    monkeypatch.setattr("app.ui.settings_tab.get_session", lambda: _FakeSession())
    monkeypatch.setattr("app.ui.settings_tab.get_staff_by_name",
                        lambda s, name: staff_lookup)
    monkeypatch.setattr("app.ui.settings_tab.get_signatures", lambda s, sid: [])
    monkeypatch.setattr("app.ui.settings_tab.get_all_staff", lambda s: [])


def test_staff_tab_hidden_for_non_admin(qtbot, monkeypatch):
    _patch_common(monkeypatch, staff_lookup=_Staff(1, "山田", is_admin=False))
    from app.ui.settings_tab import SettingsTab
    tab = SettingsTab(staff_name="山田")
    qtbot.addWidget(tab)
    inner = tab.findChild(QTabWidget)
    labels = [inner.tabText(i) for i in range(inner.count())]
    assert "職員管理" not in labels


def test_staff_tab_visible_for_admin(qtbot, monkeypatch):
    _patch_common(monkeypatch, staff_lookup=_Staff(1, "水谷", is_admin=True))
    from app.ui.settings_tab import SettingsTab
    tab = SettingsTab(staff_name="水谷")
    qtbot.addWidget(tab)
    inner = tab.findChild(QTabWidget)
    labels = [inner.tabText(i) for i in range(inner.count())]
    assert "職員管理" in labels


def test_staff_tab_hidden_when_no_staff_name(qtbot, monkeypatch):
    _patch_common(monkeypatch, staff_lookup=None)
    from app.ui.settings_tab import SettingsTab
    tab = SettingsTab()
    qtbot.addWidget(tab)
    inner = tab.findChild(QTabWidget)
    labels = [inner.tabText(i) for i in range(inner.count())]
    assert "職員管理" not in labels
```

```python
# tests/test_signature_widget_scoped.py
class _FakeSession:
    def close(self):
        pass


class _Signature:
    def __init__(self, id, name, body="", is_default=False):
        self.id = id
        self.name = name
        self.body = body
        self.is_default = is_default


def test_signature_widget_loads_only_given_staff_signatures(qtbot, monkeypatch):
    calls = []

    def fake_get_signatures(session, staff_id):
        calls.append(staff_id)
        return [_Signature(1, "自分の署名")] if staff_id == 5 else []

    monkeypatch.setattr("app.ui.settings_tab.get_session", lambda: _FakeSession())
    monkeypatch.setattr("app.ui.settings_tab.get_signatures", fake_get_signatures)

    from app.ui.settings_tab import _SignatureWidget
    w = _SignatureWidget(staff_id=5)
    qtbot.addWidget(w)

    assert calls == [5]
    assert w._table.rowCount() == 1
    assert w._table.item(0, 0).text() == "自分の署名"


def test_signature_widget_with_no_staff_id_shows_nothing(qtbot, monkeypatch):
    monkeypatch.setattr("app.ui.settings_tab.get_session", lambda: _FakeSession())

    def fail_if_called(session, staff_id):
        raise AssertionError("staff_id が None のときは get_signatures を呼ばないこと")

    monkeypatch.setattr("app.ui.settings_tab.get_signatures", fail_if_called)

    from app.ui.settings_tab import _SignatureWidget
    w = _SignatureWidget(staff_id=None)
    qtbot.addWidget(w)

    assert w._table.rowCount() == 0


def test_add_signature_uses_staff_id(qtbot, monkeypatch):
    monkeypatch.setattr("app.ui.settings_tab.get_session", lambda: _FakeSession())
    monkeypatch.setattr("app.ui.settings_tab.get_signatures", lambda s, sid: [])
    created = {}

    def fake_create_signature(session, name, body, staff_id, is_default=False):
        created["args"] = (name, body, staff_id)

    monkeypatch.setattr("app.ui.settings_tab.create_signature", fake_create_signature)

    from app.ui.settings_tab import _SignatureWidget
    w = _SignatureWidget(staff_id=7)
    qtbot.addWidget(w)
    w._name.setText("テスト署名")
    w._body.setPlainText("本文")
    w._add()

    assert created["args"] == ("テスト署名", "本文", 7)


def test_add_signature_without_staff_id_shows_warning(qtbot, monkeypatch):
    monkeypatch.setattr("app.ui.settings_tab.get_session", lambda: _FakeSession())

    def fail_if_called(session, staff_id):
        raise AssertionError("呼ばれないこと")

    monkeypatch.setattr("app.ui.settings_tab.get_signatures", fail_if_called)

    from PyQt6.QtWidgets import QMessageBox
    warned = []
    monkeypatch.setattr(QMessageBox, "warning",
                        staticmethod(lambda *a, **k: warned.append(True)))

    from app.ui.settings_tab import _SignatureWidget
    w = _SignatureWidget(staff_id=None)
    qtbot.addWidget(w)
    w._name.setText("テスト署名")
    w._body.setPlainText("本文")
    w._add()

    assert warned
```

`tests/test_signature_widget_textedit.py`を以下に置き換える:

```python
from PyQt6.QtWidgets import QTextEdit


def test_body_field_is_textedit_and_preserves_newlines(qtbot, monkeypatch):
    monkeypatch.setattr(
        "app.ui.settings_tab.get_session", lambda: _FakeSession())
    monkeypatch.setattr("app.ui.settings_tab.get_signatures", lambda s, sid: [])

    from app.ui.settings_tab import _SignatureWidget
    w = _SignatureWidget(staff_id=1)
    qtbot.addWidget(w)

    assert isinstance(w._body, QTextEdit)
    w._body.setPlainText("1行目\n2行目\n3行目")
    assert w._body.toPlainText() == "1行目\n2行目\n3行目"


class _FakeSession:
    def close(self):
        pass
```

- [ ] **Step 2: テストを実行して失敗を確認**

Run: `pytest tests/test_settings_tab_staff_admin.py tests/test_signature_widget_scoped.py tests/test_signature_widget_textedit.py -v`
Expected: FAIL — `TypeError: SettingsTab.__init__() got an unexpected keyword argument 'staff_name'`

- [ ] **Step 3: `settings_tab.py`を実装**

`app/ui/settings_tab.py`冒頭のimportに`get_staff_by_name`を追加し、`from app.services.signature_service import (...)`と`from app.services.staff_service import (...)`を以下に置き換える:

```python
from app.services.signature_service import (
    get_signatures, create_signature, update_signature,
    delete_signature, set_default
)
from app.services.staff_service import (
    get_all_staff, create_staff, set_active, set_admin, get_staff_by_name
)
```

`SettingsTab`クラス全体を以下に置き換える:

```python
class SettingsTab(QWidget):
    def __init__(self, staff_name: str = ""):
        super().__init__()
        self._staff_name = staff_name
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

`_SignatureWidget`クラス全体を以下に置き換える:

```python
class _SignatureWidget(QWidget):
    def __init__(self, staff_id: int | None):
        super().__init__()
        self._staff_id = staff_id
        layout = QVBoxLayout(self)
        self._table = QTableWidget(0, 2)
        self._table.setHorizontalHeaderLabels(["署名名", "デフォルト"])
        self._table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.itemSelectionChanged.connect(self._on_select)
        layout.addWidget(self._table)

        form = QFormLayout()
        self._name = QLineEdit()
        self._body = QTextEdit()
        self._body.setPlaceholderText("署名本文（複数行入力可）")
        self._body.setMaximumHeight(140)
        form.addRow("署名名", self._name)
        form.addRow("本文", self._body)
        layout.addLayout(form)

        btn_row = QHBoxLayout()
        btn_add = QPushButton("追加")
        btn_add.clicked.connect(self._add)
        btn_update = QPushButton("更新")
        btn_update.clicked.connect(self._update)
        btn_delete = QPushButton("削除")
        btn_delete.clicked.connect(self._delete)
        btn_default = QPushButton("デフォルトに設定")
        btn_default.clicked.connect(self._set_default)
        btn_row.addWidget(btn_add)
        btn_row.addWidget(btn_update)
        btn_row.addWidget(btn_delete)
        btn_row.addWidget(btn_default)
        btn_row.addStretch()
        layout.addLayout(btn_row)
        self._load()

    def _load(self):
        if self._staff_id is None:
            self._signatures = []
        else:
            session = get_session()
            try:
                self._signatures = get_signatures(session, self._staff_id)
            finally:
                session.close()
        self._table.setRowCount(0)
        for s in self._signatures:
            row = self._table.rowCount()
            self._table.insertRow(row)
            self._table.setItem(row, 0, QTableWidgetItem(s.name))
            self._table.setItem(row, 1, QTableWidgetItem("●" if s.is_default else ""))
            self._table.item(row, 0).setData(Qt.ItemDataRole.UserRole, s.id)

    def _on_select(self):
        row = self._table.currentRow()
        if row < 0 or row >= len(self._signatures):
            return
        s = self._signatures[row]
        self._name.setText(s.name)
        self._body.setPlainText(s.body)

    def _selected_id(self) -> int | None:
        row = self._table.currentRow()
        if row < 0:
            return None
        return self._table.item(row, 0).data(Qt.ItemDataRole.UserRole)

    def _add(self):
        name = self._name.text().strip()
        body = self._body.toPlainText()
        if not name:
            QMessageBox.warning(self, "入力エラー", "署名名を入力してください。")
            return
        if self._staff_id is None:
            QMessageBox.warning(self, "エラー", "担当者情報が取得できないため署名を保存できません。")
            return
        session = get_session()
        create_signature(session, name, body, self._staff_id)
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

    def _delete(self):
        sig_id = self._selected_id()
        if sig_id is None:
            return
        ret = QMessageBox.question(
            self, "削除確認", "この署名を削除しますか？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if ret != QMessageBox.StandardButton.Yes:
            return
        session = get_session()
        delete_signature(session, sig_id)
        session.close()
        self._load()

    def _set_default(self):
        sig_id = self._selected_id()
        if sig_id is None or self._staff_id is None:
            return
        session = get_session()
        set_default(session, sig_id, self._staff_id)
        session.close()
        self._load()
```

- [ ] **Step 4: テストを実行して成功を確認**

Run: `pytest tests/test_settings_tab_staff_admin.py tests/test_signature_widget_scoped.py tests/test_signature_widget_textedit.py tests/test_data_widget_hidden.py -v`
Expected: PASS

- [ ] **Step 5: コミット**

```bash
git add app/ui/settings_tab.py tests/test_settings_tab_staff_admin.py tests/test_signature_widget_scoped.py tests/test_signature_widget_textedit.py
git commit -m "feat: 署名を担当者スコープ化し職員管理タブを管理者限定にする"
```

---

## Task 6: `_StaffWidget`の管理者列・切替ボタン追加

**Files:**
- Modify: `app/ui/settings_tab.py`（`_StaffWidget`クラス）
- Test: `tests/test_staff_widget_admin.py`（新規）

**Interfaces:**
- Consumes: `create_staff(session, name, is_admin=False)`（Task 2）, `set_admin(session, staff_id, is_admin)`（Task 2、Task 5でimport済み）

- [ ] **Step 1: 失敗するテストを書く**

```python
# tests/test_staff_widget_admin.py
from PyQt6.QtWidgets import QMessageBox


class _FakeSession:
    def close(self):
        pass


class _Staff:
    def __init__(self, id, name, is_active=True, is_admin=False):
        self.id = id
        self.name = name
        self.is_active = is_active
        self.is_admin = is_admin


def test_staff_table_shows_admin_column(qtbot, monkeypatch):
    staff = [_Staff(1, "水谷", is_admin=True), _Staff(2, "山田", is_admin=False)]
    monkeypatch.setattr("app.ui.settings_tab.get_session", lambda: _FakeSession())
    monkeypatch.setattr("app.ui.settings_tab.get_all_staff", lambda s: staff)

    from app.ui.settings_tab import _StaffWidget
    w = _StaffWidget()
    qtbot.addWidget(w)

    assert w._table.item(0, 2).text() == "●"
    assert w._table.item(1, 2).text() == ""


def test_add_staff_with_admin_checkbox(qtbot, monkeypatch):
    monkeypatch.setattr("app.ui.settings_tab.get_session", lambda: _FakeSession())
    monkeypatch.setattr("app.ui.settings_tab.get_all_staff", lambda s: [])
    created = {}

    def fake_create_staff(session, name, is_admin=False):
        created["args"] = (name, is_admin)

    monkeypatch.setattr("app.ui.settings_tab.create_staff", fake_create_staff)

    from app.ui.settings_tab import _StaffWidget
    w = _StaffWidget()
    qtbot.addWidget(w)
    w._name.setText("新人")
    w._chk_admin.setChecked(True)
    w._add()

    assert created["args"] == ("新人", True)


def test_toggle_admin_warns_when_removing_last_admin(qtbot, monkeypatch):
    staff = [_Staff(1, "水谷", is_admin=True)]
    monkeypatch.setattr("app.ui.settings_tab.get_session", lambda: _FakeSession())
    monkeypatch.setattr("app.ui.settings_tab.get_all_staff", lambda s: staff)
    warned = []
    monkeypatch.setattr(
        QMessageBox, "question",
        staticmethod(lambda *a, **k: (warned.append(True),
                                       QMessageBox.StandardButton.No)[1]))
    toggled = []
    monkeypatch.setattr(
        "app.ui.settings_tab.set_admin",
        lambda session, sid, is_admin: toggled.append((sid, is_admin)))

    from app.ui.settings_tab import _StaffWidget
    w = _StaffWidget()
    qtbot.addWidget(w)
    w._table.setCurrentCell(0, 0)
    w._toggle_admin()

    assert warned, "最後の管理者を外そうとした際に警告が出ること"
    assert toggled == [], "Noを選んだ場合はset_adminが呼ばれないこと"


def test_toggle_admin_works_when_other_admin_exists(qtbot, monkeypatch):
    staff = [_Staff(1, "水谷", is_admin=True), _Staff(2, "山田", is_admin=True)]
    monkeypatch.setattr("app.ui.settings_tab.get_session", lambda: _FakeSession())
    monkeypatch.setattr("app.ui.settings_tab.get_all_staff", lambda s: staff)
    toggled = []
    monkeypatch.setattr(
        "app.ui.settings_tab.set_admin",
        lambda session, sid, is_admin: toggled.append((sid, is_admin)))

    from app.ui.settings_tab import _StaffWidget
    w = _StaffWidget()
    qtbot.addWidget(w)
    w._table.setCurrentCell(0, 0)
    w._toggle_admin()

    assert toggled == [(1, False)], "他に管理者がいれば確認なしで切り替わること"
```

- [ ] **Step 2: テストを実行して失敗を確認**

Run: `pytest tests/test_staff_widget_admin.py -v`
Expected: FAIL — `AttributeError: '_StaffWidget' object has no attribute '_chk_admin'`

- [ ] **Step 3: `_StaffWidget`を実装**

`_StaffWidget`クラス全体を以下に置き換える:

```python
class _StaffWidget(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        self._table = QTableWidget(0, 3)
        self._table.setHorizontalHeaderLabels(["職員名", "有効", "管理者"])
        self._table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self._table)

        form = QFormLayout()
        self._name = QLineEdit()
        form.addRow("職員名", self._name)
        self._chk_admin = QCheckBox("管理者にする")
        form.addRow("", self._chk_admin)
        layout.addLayout(form)

        btn_row = QHBoxLayout()
        btn_add = QPushButton("追加")
        btn_add.clicked.connect(self._add)
        btn_toggle = QPushButton("有効/無効切り替え")
        btn_toggle.clicked.connect(self._toggle)
        btn_admin = QPushButton("管理者権限 切替")
        btn_admin.clicked.connect(self._toggle_admin)
        btn_row.addWidget(btn_add)
        btn_row.addWidget(btn_toggle)
        btn_row.addWidget(btn_admin)
        btn_row.addStretch()
        layout.addLayout(btn_row)
        self._load()

    def _load(self):
        session = get_session()
        try:
            self._staff = get_all_staff(session)
        finally:
            session.close()
        self._table.setRowCount(0)
        for s in self._staff:
            row = self._table.rowCount()
            self._table.insertRow(row)
            self._table.setItem(row, 0, QTableWidgetItem(s.name))
            self._table.setItem(row, 1, QTableWidgetItem("○" if s.is_active else "×"))
            self._table.setItem(row, 2, QTableWidgetItem("●" if s.is_admin else ""))
            self._table.item(row, 0).setData(Qt.ItemDataRole.UserRole, s.id)

    def _add(self):
        name = self._name.text().strip()
        if not name:
            QMessageBox.warning(self, "入力エラー", "職員名を入力してください。")
            return
        session = get_session()
        create_staff(session, name, is_admin=self._chk_admin.isChecked())
        session.close()
        self._name.clear()
        self._chk_admin.setChecked(False)
        self._load()

    def _toggle(self):
        row = self._table.currentRow()
        if row < 0 or row >= len(self._staff):
            return
        s = self._staff[row]
        session = get_session()
        set_active(session, s.id, not s.is_active)
        session.close()
        self._load()

    def _toggle_admin(self):
        row = self._table.currentRow()
        if row < 0 or row >= len(self._staff):
            return
        s = self._staff[row]
        if s.is_admin:
            other_admins = [x for x in self._staff if x.is_admin and x.id != s.id]
            if not other_admins:
                ret = QMessageBox.question(
                    self, "最後の管理者です",
                    f"「{s.name}」は現在唯一の管理者です。管理者権限を外すと、"
                    "職員管理タブに誰もアクセスできなくなります。続行しますか？",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No)
                if ret != QMessageBox.StandardButton.Yes:
                    return
        session = get_session()
        set_admin(session, s.id, not s.is_admin)
        session.close()
        self._load()
```

- [ ] **Step 4: テストを実行して成功を確認**

Run: `pytest tests/test_staff_widget_admin.py -v`
Expected: PASS

- [ ] **Step 5: コミット**

```bash
git add app/ui/settings_tab.py tests/test_staff_widget_admin.py
git commit -m "feat: 職員管理に管理者フラグの表示・切替を追加"
```

---

## Task 7: `SendTab`の署名コンボを担当者スコープに

**Files:**
- Modify: `app/ui/send_tab.py`（`_load_combos`）
- Test: `tests/test_send_tab_signature_scope.py`（新規）

**Interfaces:**
- Consumes: `get_signatures(session, staff_id)` / `get_default_signature(session, staff_id)`（Task 3）, `get_staff_by_name(session, name)`（既存、`send_tab.py`に既にimport済み）

- [ ] **Step 1: 失敗するテストを書く**

```python
# tests/test_send_tab_signature_scope.py
class _FakeSession:
    def close(self):
        pass


class _Staff:
    def __init__(self, id, name):
        self.id = id
        self.name = name


class _Signature:
    def __init__(self, id, name):
        self.id = id
        self.name = name


def _patch_common(monkeypatch, staff=None, signatures=None):
    monkeypatch.setattr("app.ui.send_tab.get_session", lambda: _FakeSession())
    monkeypatch.setattr("app.ui.send_tab.get_positions", lambda s: [])
    monkeypatch.setattr("app.ui.send_tab.get_committees", lambda s: [])
    monkeypatch.setattr("app.ui.send_tab.get_members", lambda s: [])
    monkeypatch.setattr("app.ui.send_tab.get_templates", lambda s: [])
    monkeypatch.setattr("app.ui.send_tab.get_staff_by_name", lambda s, name: staff)
    monkeypatch.setattr("app.ui.send_tab.get_signatures", lambda s, sid: signatures or [])
    monkeypatch.setattr("app.ui.send_tab.get_default_signature", lambda s, sid: None)


def test_signature_combo_shows_only_own_signatures(qtbot, monkeypatch):
    staff = _Staff(3, "水谷")
    sigs = [_Signature(10, "水谷の署名")]
    _patch_common(monkeypatch, staff=staff, signatures=sigs)

    from app.ui.send_tab import SendTab
    tab = SendTab(staff_name="水谷")
    qtbot.addWidget(tab)

    labels = [tab._sig_combo.itemText(i) for i in range(tab._sig_combo.count())]
    assert "水谷の署名" in labels


def test_signature_combo_empty_when_staff_not_found(qtbot, monkeypatch):
    _patch_common(monkeypatch, staff=None, signatures=[])
    from app.ui.send_tab import SendTab
    tab = SendTab(staff_name="不明")
    qtbot.addWidget(tab)

    assert tab._sig_combo.count() == 1  # "（なし）"のみ
```

- [ ] **Step 2: テストを実行して失敗を確認**

Run: `pytest tests/test_send_tab_signature_scope.py -v`
Expected: FAIL — `TypeError: get_signatures() missing 1 required positional argument: 'staff_id'`

- [ ] **Step 3: `_load_combos`を修正**

`app/ui/send_tab.py`の`_load_combos`メソッド内、`self._signatures = get_signatures(session)`から`default_sig`の`if`ブロック終わりまでを以下に置き換える:

```python
            staff = get_staff_by_name(session, self._staff_name) if self._staff_name else None
            staff_id = staff.id if staff else None
            self._signatures = get_signatures(session, staff_id) if staff_id else []
            self._sig_combo.clear()
            self._sig_combo.addItem("（なし）", None)
            for s in self._signatures:
                self._sig_combo.addItem(s.name, s.id)
            default_sig = get_default_signature(session, staff_id) if staff_id else None
            if default_sig:
                for i in range(self._sig_combo.count()):
                    if self._sig_combo.itemData(i) == default_sig.id:
                        self._sig_combo.setCurrentIndex(i)
                        break
```

- [ ] **Step 4: テストを実行して成功を確認**

Run: `pytest tests/test_send_tab_signature_scope.py -v`
Expected: PASS

- [ ] **Step 5: コミット**

```bash
git add app/ui/send_tab.py tests/test_send_tab_signature_scope.py
git commit -m "feat: 送信タブの署名選択を担当者スコープに変更"
```

---

## Task 8: `TemplateTab`の署名コンボを担当者スコープに

**Files:**
- Modify: `app/ui/template_tab.py`（import、`TemplateTab.__init__`、`_load`）
- Test: `tests/test_template_tab_signature_scope.py`（新規）

**Interfaces:**
- Consumes: `get_signatures(session, staff_id)`（Task 3）, `get_staff_by_name(session, name)`（既存、`staff_service.py`）
- Produces: `TemplateTab.__init__(self, staff_name: str = "")`, `TemplateTab._staff_name`

- [ ] **Step 1: 失敗するテストを書く**

```python
# tests/test_template_tab_signature_scope.py
class _FakeSession:
    def close(self):
        pass


class _Staff:
    def __init__(self, id, name):
        self.id = id
        self.name = name


class _Signature:
    def __init__(self, id, name):
        self.id = id
        self.name = name


def test_template_tab_signature_combo_scoped_to_staff(qtbot, monkeypatch):
    staff = _Staff(4, "山田")
    sigs = [_Signature(20, "山田の署名")]
    monkeypatch.setattr("app.ui.template_tab.get_session", lambda: _FakeSession())
    monkeypatch.setattr("app.ui.template_tab.get_templates", lambda s: [])
    monkeypatch.setattr("app.ui.template_tab.get_staff_by_name", lambda s, name: staff)
    monkeypatch.setattr(
        "app.ui.template_tab.get_signatures",
        lambda s, sid: sigs if sid == 4 else [])

    from app.ui.template_tab import TemplateTab
    tab = TemplateTab(staff_name="山田")
    qtbot.addWidget(tab)

    labels = [tab._sig_combo.itemText(i) for i in range(tab._sig_combo.count())]
    assert "山田の署名" in labels


def test_template_tab_without_staff_name_shows_no_signatures(qtbot, monkeypatch):
    monkeypatch.setattr("app.ui.template_tab.get_session", lambda: _FakeSession())
    monkeypatch.setattr("app.ui.template_tab.get_templates", lambda s: [])
    monkeypatch.setattr("app.ui.template_tab.get_staff_by_name", lambda s, name: None)

    def fail_if_called(session, staff_id):
        raise AssertionError("staff_id が None のときは get_signatures を呼ばないこと")

    monkeypatch.setattr("app.ui.template_tab.get_signatures", fail_if_called)

    from app.ui.template_tab import TemplateTab
    tab = TemplateTab()
    qtbot.addWidget(tab)

    assert tab._sig_combo.count() == 1
```

- [ ] **Step 2: テストを実行して失敗を確認**

Run: `pytest tests/test_template_tab_signature_scope.py -v`
Expected: FAIL — `TypeError: TemplateTab.__init__() got an unexpected keyword argument 'staff_name'`

- [ ] **Step 3: `template_tab.py`を実装**

`app/ui/template_tab.py`冒頭のimportに以下を追加する（`from app.services.signature_service import get_signatures`の直後）:

```python
from app.services.staff_service import get_staff_by_name
```

`TemplateTab.__init__`を以下に置き換える:

```python
class TemplateTab(QWidget):
    def __init__(self, staff_name: str = ""):
        super().__init__()
        self._staff_name = staff_name
        self._current_id: int | None = None
        self._snapshot: tuple = ("", "", "", None)
        self._build()
        self._load()
```

`_load`メソッド内の`self._signatures = get_signatures(session)`を以下に置き換える:

```python
            staff = get_staff_by_name(session, self._staff_name) if self._staff_name else None
            staff_id = staff.id if staff else None
            self._signatures = get_signatures(session, staff_id) if staff_id else []
```

- [ ] **Step 4: テストを実行して成功を確認**

Run: `pytest tests/test_template_tab_signature_scope.py -v`
Expected: PASS

- [ ] **Step 5: コミット**

```bash
git add app/ui/template_tab.py tests/test_template_tab_signature_scope.py
git commit -m "feat: テンプレートタブの署名選択を担当者スコープに変更"
```

---

## Task 9: `main_window.py`の配線更新

**Files:**
- Modify: `app/ui/main_window.py`（`_build_tabs`）
- Test: `tests/test_main_window_staff_wiring.py`（新規）

**Interfaces:**
- Consumes: `SettingsTab(staff_name=...)`（Task 5）, `TemplateTab(staff_name=...)`（Task 8）

- [ ] **Step 1: 失敗するテストを書く**

```python
# tests/test_main_window_staff_wiring.py
from PyQt6.QtWidgets import QTabWidget


def test_settings_and_template_tabs_receive_staff_name(qtbot):
    from app.ui.main_window import MainWindow
    window = MainWindow(staff_name="水谷")
    qtbot.addWidget(window)

    tab_widget = window.findChild(QTabWidget)
    template_tab = None
    settings_tab = None
    for i in range(tab_widget.count()):
        if tab_widget.tabText(i) == "テンプレート":
            template_tab = tab_widget.widget(i)
        elif tab_widget.tabText(i) == "設定":
            settings_tab = tab_widget.widget(i)

    assert template_tab is not None and template_tab._staff_name == "水谷"
    assert settings_tab is not None and settings_tab._staff_name == "水谷"
```

（このテストは`tests/test_main_window.py`と同様、実データベースに依存する既存の慣例に倣う。新しいモック導入は行わない。）

- [ ] **Step 2: テストを実行して失敗を確認**

Run: `pytest tests/test_main_window_staff_wiring.py -v`
Expected: FAIL — `AttributeError: 'TemplateTab' object has no attribute '_staff_name'`（現状`TemplateTab()`は`staff_name`を受け取らず保持もしていないため）

- [ ] **Step 3: `_build_tabs`を修正**

`app/ui/main_window.py`の`_build_tabs`メソッド内、以下2行を:

```python
            tabs.addTab(TemplateTab(), "テンプレート")
            tabs.addTab(SettingsTab(), "設定")
```

以下に置き換える:

```python
            tabs.addTab(TemplateTab(staff_name=self._staff_name), "テンプレート")
            tabs.addTab(SettingsTab(staff_name=self._staff_name), "設定")
```

- [ ] **Step 4: テストを実行して成功を確認**

Run: `pytest tests/test_main_window_staff_wiring.py tests/test_main_window.py -v`
Expected: PASS

- [ ] **Step 5: コミット**

```bash
git add app/ui/main_window.py tests/test_main_window_staff_wiring.py
git commit -m "feat: メインウィンドウからテンプレートタブ・設定タブに担当者名を渡す"
```

---

## 全体テスト実行（最終確認）

全タスク完了後、既存スイートを含めて回帰がないことを確認する。

Run: `pytest -v`
Expected: 既存テストすべて + 本計画で追加したテストすべてが PASS

## タスク完了後の手動作業（コントローラーが実施、サブエージェントには含めない）

全タスク完了後、実際の運用DBに対して以下を一度だけ実行する（自動マイグレーションには含めない）:

```python
from app.database.connection import get_session
from app.services.staff_service import get_staff_by_name, set_admin

session = get_session()
staff = get_staff_by_name(session, "水谷")
if staff:
    set_admin(session, staff.id, True)
session.close()
```

実行前にユーザーに確認を取ること。
