# cci-mail Plan 3: テンプレート・署名・設定タブ

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** メールテンプレート管理・署名管理・会議所役職マスタ・職員管理・Microsoft 365設定を実装し、テンプレートタブと設定タブを完成させる。

**Architecture:** `template_service.py`・`signature_service.py` でDB操作をカプセル化。設定タブはサブタブ構成（Graph API設定 / 署名管理 / 役職マスタ / 職員管理）。

**Tech Stack:** Python 3.11+, PyQt6, SQLAlchemy 2.x, pytest

## Global Constraints

- Plan 1・Plan 2が完了していること
- テストはインメモリSQLite（conftest.pyのdb_sessionフィクスチャ）を使用
- Graph API設定はapp_config.jsonに保存（DBではなく）
- クライアントシークレットは画面上 `****` でマスク表示

---

## ファイル構成（新規作成・変更）

```
app/
  services/
    template_service.py    # 新規作成
    signature_service.py   # 新規作成
    position_service.py    # 新規作成
    staff_service.py       # 新規作成
  ui/
    template_tab.py        # Plan 1プレースホルダーを置き換え
    settings_tab.py        # Plan 1プレースホルダーを置き換え
tests/
  test_template_service.py
  test_signature_service.py
  test_position_service.py
  test_staff_service.py
```

---

## Task 1: サービス層（テンプレート・署名・役職・職員）

**Files:**
- Create: `app/services/template_service.py`
- Create: `app/services/signature_service.py`
- Create: `app/services/position_service.py`
- Create: `app/services/staff_service.py`
- Create: `tests/test_template_service.py`
- Create: `tests/test_signature_service.py`
- Create: `tests/test_position_service.py`
- Create: `tests/test_staff_service.py`

**Interfaces:**
- Produces:
  - `template_service.create_template(session, name, subject, body, signature_id=None) -> EmailTemplate`
  - `template_service.update_template(session, template_id, **kwargs) -> EmailTemplate`
  - `template_service.delete_template(session, template_id) -> None`
  - `template_service.get_templates(session) -> list[EmailTemplate]`
  - `template_service.get_template(session, template_id) -> EmailTemplate | None`
  - `signature_service.create_signature(session, name, body, is_default=False) -> Signature`
  - `signature_service.update_signature(session, sig_id, **kwargs) -> Signature`
  - `signature_service.delete_signature(session, sig_id) -> None`
  - `signature_service.get_signatures(session) -> list[Signature]`
  - `signature_service.get_default_signature(session) -> Signature | None`
  - `signature_service.set_default(session, sig_id) -> None`
  - `position_service.create_position(session, name, sort_order) -> Position`
  - `position_service.update_position(session, pos_id, **kwargs) -> Position`
  - `position_service.delete_position(session, pos_id) -> None`
  - `position_service.get_positions(session) -> list[Position]`
  - `staff_service.create_staff(session, name) -> Staff`
  - `staff_service.get_active_staff(session) -> list[Staff]`
  - `staff_service.set_active(session, staff_id, is_active: bool) -> None`

- [ ] **Step 1: テストを書く**

```python
# tests/test_template_service.py
from app.services.template_service import (
    create_template, update_template, delete_template,
    get_templates, get_template
)
from app.services.signature_service import create_signature


def test_create_and_get_template(db_session):
    t = create_template(db_session, "総会案内", "総会のご案内", "本文テスト")
    assert t.id is not None
    fetched = get_template(db_session, t.id)
    assert fetched.name == "総会案内"


def test_create_template_with_signature(db_session):
    sig = create_signature(db_session, "標準署名", "商工会議所\n担当：田中")
    t = create_template(db_session, "総会案内", "件名", "本文", signature_id=sig.id)
    fetched = get_template(db_session, t.id)
    assert fetched.signature.name == "標準署名"


def test_update_template(db_session):
    t = create_template(db_session, "案内", "件名", "本文")
    update_template(db_session, t.id, subject="新件名")
    fetched = get_template(db_session, t.id)
    assert fetched.subject == "新件名"


def test_delete_template(db_session):
    t = create_template(db_session, "案内", "件名", "本文")
    delete_template(db_session, t.id)
    assert get_template(db_session, t.id) is None


def test_get_templates_returns_all(db_session):
    create_template(db_session, "案内1", "件名1", "本文1")
    create_template(db_session, "案内2", "件名2", "本文2")
    templates = get_templates(db_session)
    assert len(templates) == 2
```

```python
# tests/test_signature_service.py
from app.services.signature_service import (
    create_signature, update_signature, delete_signature,
    get_signatures, get_default_signature, set_default
)


def test_create_signature(db_session):
    sig = create_signature(db_session, "標準署名", "商工会議所")
    assert sig.id is not None
    assert not sig.is_default


def test_set_default_clears_others(db_session):
    sig1 = create_signature(db_session, "署名A", "本文A", is_default=True)
    sig2 = create_signature(db_session, "署名B", "本文B")
    set_default(db_session, sig2.id)
    default = get_default_signature(db_session)
    assert default.id == sig2.id
    db_session.refresh(sig1)
    assert not sig1.is_default


def test_get_default_returns_none_when_no_default(db_session):
    create_signature(db_session, "署名A", "本文A")
    assert get_default_signature(db_session) is None
```

```python
# tests/test_position_service.py
from app.services.position_service import (
    create_position, update_position, delete_position, get_positions
)


def test_create_position(db_session):
    pos = create_position(db_session, "会頭", 1)
    assert pos.id is not None
    assert pos.name == "会頭"


def test_get_positions_sorted(db_session):
    create_position(db_session, "議員", 10)
    create_position(db_session, "会頭", 1)
    positions = get_positions(db_session)
    assert positions[0].name == "会頭"
    assert positions[1].name == "議員"


def test_delete_position(db_session):
    pos = create_position(db_session, "会頭", 1)
    delete_position(db_session, pos.id)
    assert len(get_positions(db_session)) == 0
```

```python
# tests/test_staff_service.py
from app.services.staff_service import (
    create_staff, get_active_staff, set_active
)


def test_create_and_get_staff(db_session):
    s = create_staff(db_session, "田中")
    staff = get_active_staff(db_session)
    assert len(staff) == 1
    assert staff[0].name == "田中"


def test_inactive_staff_excluded(db_session):
    s = create_staff(db_session, "田中")
    set_active(db_session, s.id, False)
    assert len(get_active_staff(db_session)) == 0
```

- [ ] **Step 2: テスト実行 → 失敗確認**

```bash
pytest tests/test_template_service.py tests/test_signature_service.py tests/test_position_service.py tests/test_staff_service.py -v
```

期待: `ImportError`

- [ ] **Step 3: 4つのサービスを作成**

```python
# app/services/template_service.py
from sqlalchemy.orm import Session
from app.database.models import EmailTemplate


def create_template(session: Session, name: str, subject: str, body: str,
                    signature_id: int | None = None) -> EmailTemplate:
    t = EmailTemplate(name=name, subject=subject, body=body,
                      signature_id=signature_id)
    session.add(t)
    session.commit()
    return t


def get_template(session: Session, template_id: int) -> EmailTemplate | None:
    return session.get(EmailTemplate, template_id)


def get_templates(session: Session) -> list[EmailTemplate]:
    return session.query(EmailTemplate).order_by(EmailTemplate.name).all()


def update_template(session: Session, template_id: int, **kwargs) -> EmailTemplate:
    t = session.get(EmailTemplate, template_id)
    if t is None:
        raise ValueError(f"テンプレートID {template_id} が見つかりません")
    for k, v in kwargs.items():
        setattr(t, k, v)
    session.commit()
    return t


def delete_template(session: Session, template_id: int) -> None:
    t = session.get(EmailTemplate, template_id)
    if t:
        session.delete(t)
        session.commit()
```

```python
# app/services/signature_service.py
from sqlalchemy.orm import Session
from app.database.models import Signature


def create_signature(session: Session, name: str, body: str,
                     is_default: bool = False) -> Signature:
    sig = Signature(name=name, body=body, is_default=is_default)
    session.add(sig)
    session.commit()
    return sig


def get_signatures(session: Session) -> list[Signature]:
    return session.query(Signature).order_by(Signature.name).all()


def get_default_signature(session: Session) -> Signature | None:
    return session.query(Signature).filter_by(is_default=True).first()


def set_default(session: Session, sig_id: int) -> None:
    session.query(Signature).update({"is_default": False})
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

```python
# app/services/position_service.py
from sqlalchemy.orm import Session
from app.database.models import Position


def create_position(session: Session, name: str, sort_order: int) -> Position:
    pos = Position(name=name, sort_order=sort_order)
    session.add(pos)
    session.commit()
    return pos


def get_positions(session: Session) -> list[Position]:
    return session.query(Position).order_by(Position.sort_order).all()


def update_position(session: Session, pos_id: int, **kwargs) -> Position:
    pos = session.get(Position, pos_id)
    if pos is None:
        raise ValueError(f"役職ID {pos_id} が見つかりません")
    for k, v in kwargs.items():
        setattr(pos, k, v)
    session.commit()
    return pos


def delete_position(session: Session, pos_id: int) -> None:
    pos = session.get(Position, pos_id)
    if pos:
        session.delete(pos)
        session.commit()
```

```python
# app/services/staff_service.py
from sqlalchemy.orm import Session
from app.database.models import Staff


def create_staff(session: Session, name: str) -> Staff:
    s = Staff(name=name, is_active=True)
    session.add(s)
    session.commit()
    return s


def get_active_staff(session: Session) -> list[Staff]:
    return (session.query(Staff)
            .filter_by(is_active=True)
            .order_by(Staff.name)
            .all())


def get_all_staff(session: Session) -> list[Staff]:
    return session.query(Staff).order_by(Staff.name).all()


def set_active(session: Session, staff_id: int, is_active: bool) -> None:
    s = session.get(Staff, staff_id)
    if s:
        s.is_active = is_active
        session.commit()
```

- [ ] **Step 4: テスト実行 → パス確認**

```bash
pytest tests/test_template_service.py tests/test_signature_service.py tests/test_position_service.py tests/test_staff_service.py -v
```

期待: `12 passed`

- [ ] **Step 5: コミット**

```bash
git add app/services/template_service.py app/services/signature_service.py \
        app/services/position_service.py app/services/staff_service.py \
        tests/test_template_service.py tests/test_signature_service.py \
        tests/test_position_service.py tests/test_staff_service.py
git commit -m "feat: テンプレート・署名・役職・職員サービスを追加"
```

---

## Task 2: テンプレートタブ

**Files:**
- Modify: `app/ui/template_tab.py`（プレースホルダーを置き換え）

**Interfaces:**
- Consumes: `get_templates()`, `create_template()`, `update_template()`, `delete_template()`、`get_signatures()`

- [ ] **Step 1: template_tab.py を実装**

```python
# app/ui/template_tab.py
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QListWidget, QListWidgetItem, QPushButton,
    QFormLayout, QLineEdit, QTextEdit, QComboBox,
    QLabel, QGroupBox, QMessageBox
)
from PyQt6.QtCore import Qt
from app.database.connection import get_session
from app.services.template_service import (
    get_templates, create_template, update_template, delete_template
)
from app.services.signature_service import get_signatures

_PLACEHOLDERS = [
    "{事業所名}", "{役職名}", "{氏名}", "{会議所役職名}",
    "{col1}", "{col2}", "{col3}", "{col4}", "{col5}",
]


class TemplateTab(QWidget):
    def __init__(self):
        super().__init__()
        self._current_id: int | None = None
        self._build()
        self._load()

    def _build(self):
        layout = QVBoxLayout(self)
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # 左ペイン：テンプレート一覧
        left = QWidget()
        left_layout = QVBoxLayout(left)
        self._list = QListWidget()
        self._list.currentRowChanged.connect(self._on_select)
        btn_row = QHBoxLayout()
        btn_new = QPushButton("新規")
        btn_new.clicked.connect(self._new)
        btn_delete = QPushButton("削除")
        btn_delete.clicked.connect(self._delete)
        btn_row.addWidget(btn_new)
        btn_row.addWidget(btn_delete)
        left_layout.addWidget(QLabel("テンプレート一覧"))
        left_layout.addWidget(self._list)
        left_layout.addLayout(btn_row)
        splitter.addWidget(left)

        # 右ペイン：編集フォーム
        right = QWidget()
        right_layout = QVBoxLayout(right)
        form_grp = QGroupBox("テンプレート編集")
        form = QFormLayout(form_grp)
        self._name = QLineEdit()
        self._subject = QLineEdit()
        self._body = QTextEdit()
        self._body.setMinimumHeight(200)
        self._sig_combo = QComboBox()
        form.addRow("テンプレート名", self._name)
        form.addRow("件名", self._subject)
        form.addRow("本文", self._body)
        form.addRow("デフォルト署名", self._sig_combo)
        right_layout.addWidget(form_grp)

        ph_grp = QGroupBox("使用可能なプレースホルダー")
        ph_layout = QVBoxLayout(ph_grp)
        ph_layout.addWidget(QLabel("  ".join(_PLACEHOLDERS)))
        ph_layout.addWidget(QLabel(
            "差し込みデータ: {col1}〜{col5}は送信時にCSV/Excelからインポートした値に置換されます"))
        right_layout.addWidget(ph_grp)

        btn_save = QPushButton("保存")
        btn_save.clicked.connect(self._save)
        right_layout.addWidget(btn_save)
        splitter.addWidget(right)

        splitter.setSizes([200, 500])
        layout.addWidget(splitter)

    def _load(self):
        session = get_session()
        try:
            self._templates = get_templates(session)
            self._signatures = get_signatures(session)
        finally:
            session.close()

        self._list.blockSignals(True)
        self._list.clear()
        for t in self._templates:
            item = QListWidgetItem(t.name)
            item.setData(Qt.ItemDataRole.UserRole, t.id)
            self._list.addItem(item)
        self._list.blockSignals(False)

        self._sig_combo.blockSignals(True)
        self._sig_combo.clear()
        self._sig_combo.addItem("（なし）", None)
        for s in self._signatures:
            self._sig_combo.addItem(s.name, s.id)
        self._sig_combo.blockSignals(False)

    def _on_select(self, row: int):
        if row < 0 or row >= len(self._templates):
            return
        t = self._templates[row]
        self._current_id = t.id
        self._name.setText(t.name)
        self._subject.setText(t.subject)
        self._body.setPlainText(t.body)
        for i in range(self._sig_combo.count()):
            if self._sig_combo.itemData(i) == t.signature_id:
                self._sig_combo.setCurrentIndex(i)
                break

    def _new(self):
        self._current_id = None
        self._name.clear()
        self._subject.clear()
        self._body.clear()
        self._sig_combo.setCurrentIndex(0)
        self._list.clearSelection()

    def _save(self):
        name = self._name.text().strip()
        subject = self._subject.text().strip()
        body = self._body.toPlainText().strip()
        if not name or not subject:
            QMessageBox.warning(self, "入力エラー", "テンプレート名と件名は必須です。")
            return
        sig_id = self._sig_combo.currentData()
        session = get_session()
        try:
            if self._current_id:
                update_template(session, self._current_id,
                                name=name, subject=subject,
                                body=body, signature_id=sig_id)
            else:
                create_template(session, name, subject, body,
                                signature_id=sig_id)
        except Exception as e:
            QMessageBox.critical(self, "エラー", str(e))
            return
        finally:
            session.close()
        self._load()

    def _delete(self):
        if self._current_id is None:
            return
        ret = QMessageBox.question(
            self, "削除確認", "このテンプレートを削除しますか？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if ret != QMessageBox.StandardButton.Yes:
            return
        session = get_session()
        delete_template(session, self._current_id)
        session.close()
        self._current_id = None
        self._new()
        self._load()
```

- [ ] **Step 2: コミット**

```bash
git add app/ui/template_tab.py
git commit -m "feat: テンプレートタブ（CRUD・プレースホルダー表示）を実装"
```

---

## Task 3: 設定タブ

**Files:**
- Modify: `app/ui/settings_tab.py`（プレースホルダーを置き換え）

**Interfaces:**
- Consumes: `get_config()`, `save_config()`, `get_graph_config()`（app_config.py）、`get_signatures()`, `create_signature()`, `update_signature()`, `delete_signature()`, `set_default()`（signature_service.py）、`get_positions()`, `create_position()`, `update_position()`, `delete_position()`（position_service.py）、`get_all_staff()`, `create_staff()`, `set_active()`（staff_service.py）

- [ ] **Step 1: settings_tab.py を実装**

```python
# app/ui/settings_tab.py
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QTabWidget, QFormLayout, QHBoxLayout,
    QLineEdit, QPushButton, QGroupBox, QTableWidget, QTableWidgetItem,
    QCheckBox, QMessageBox, QHeaderView, QLabel, QSpinBox
)
from PyQt6.QtCore import Qt
from app.utils.app_config import get_config, save_config
from app.database.connection import get_session
from app.services.signature_service import (
    get_signatures, create_signature, update_signature,
    delete_signature, set_default
)
from app.services.position_service import (
    get_positions, create_position, update_position, delete_position
)
from app.services.staff_service import get_all_staff, create_staff, set_active


class SettingsTab(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        inner = QTabWidget()
        inner.addTab(_GraphSettingsWidget(), "Microsoft 365")
        inner.addTab(_SignatureWidget(), "署名管理")
        inner.addTab(_PositionWidget(), "会議所役職")
        inner.addTab(_StaffWidget(), "職員管理")
        layout.addWidget(inner)


class _GraphSettingsWidget(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        grp = QGroupBox("Microsoft 365 / Graph API 設定")
        form = QFormLayout(grp)
        self._tenant_id = QLineEdit()
        self._client_id = QLineEdit()
        self._client_secret = QLineEdit()
        self._client_secret.setEchoMode(QLineEdit.EchoMode.Password)
        self._from_address = QLineEdit()
        self._test_address = QLineEdit()
        form.addRow("テナントID", self._tenant_id)
        form.addRow("クライアントID", self._client_id)
        form.addRow("クライアントシークレット", self._client_secret)
        form.addRow("送信元アドレス", self._from_address)
        form.addRow("テスト送信先", self._test_address)
        layout.addWidget(grp)
        btn_row = QHBoxLayout()
        btn_save = QPushButton("設定を保存")
        btn_save.clicked.connect(self._save)
        btn_test = QPushButton("接続テスト")
        btn_test.clicked.connect(self._test_connection)
        btn_row.addWidget(btn_save)
        btn_row.addWidget(btn_test)
        btn_row.addStretch()
        layout.addLayout(btn_row)
        layout.addStretch()
        self._load()

    def _load(self):
        cfg = get_config().get("graph", {})
        self._tenant_id.setText(cfg.get("tenant_id", ""))
        self._client_id.setText(cfg.get("client_id", ""))
        self._client_secret.setText(cfg.get("client_secret", ""))
        self._from_address.setText(cfg.get("from_address", ""))
        self._test_address.setText(cfg.get("test_address", ""))

    def _save(self):
        config = get_config()
        config["graph"] = {
            "tenant_id":     self._tenant_id.text().strip(),
            "client_id":     self._client_id.text().strip(),
            "client_secret": self._client_secret.text(),
            "from_address":  self._from_address.text().strip(),
            "test_address":  self._test_address.text().strip(),
        }
        save_config(config)
        QMessageBox.information(self, "保存", "設定を保存しました。")

    def _test_connection(self):
        self._save()
        try:
            import msal
            cfg = get_config().get("graph", {})
            app = msal.ConfidentialClientApplication(
                cfg["client_id"],
                authority=f"https://login.microsoftonline.com/{cfg['tenant_id']}",
                client_credential=cfg["client_secret"],
            )
            result = app.acquire_token_for_client(
                scopes=["https://graph.microsoft.com/.default"]
            )
            if "access_token" in result:
                QMessageBox.information(self, "成功", "Microsoft 365への接続に成功しました。")
            else:
                QMessageBox.critical(self, "失敗",
                                     f"トークン取得失敗: {result.get('error_description', '')}")
        except Exception as e:
            QMessageBox.critical(self, "エラー", str(e))


class _SignatureWidget(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        self._table = QTableWidget(0, 2)
        self._table.setHorizontalHeaderLabels(["署名名", "デフォルト"])
        self._table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.currentRowChanged.connect(self._on_select)
        layout.addWidget(self._table)

        form = QFormLayout()
        self._name = QLineEdit()
        self._body = QLineEdit()
        self._body.setPlaceholderText("署名本文（複数行は\\nで区切る）")
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
        session = get_session()
        try:
            self._signatures = get_signatures(session)
        finally:
            session.close()
        self._table.setRowCount(0)
        for s in self._signatures:
            row = self._table.rowCount()
            self._table.insertRow(row)
            self._table.setItem(row, 0, QTableWidgetItem(s.name))
            self._table.setItem(row, 1, QTableWidgetItem("●" if s.is_default else ""))
            self._table.item(row, 0).setData(Qt.ItemDataRole.UserRole, s.id)

    def _on_select(self, row: int):
        if row < 0 or row >= len(self._signatures):
            return
        s = self._signatures[row]
        self._name.setText(s.name)
        self._body.setText(s.body.replace("\n", "\\n"))

    def _selected_id(self) -> int | None:
        row = self._table.currentRow()
        if row < 0:
            return None
        return self._table.item(row, 0).data(Qt.ItemDataRole.UserRole)

    def _add(self):
        name = self._name.text().strip()
        body = self._body.text().replace("\\n", "\n")
        if not name:
            return
        session = get_session()
        create_signature(session, name, body)
        session.close()
        self._load()

    def _update(self):
        sig_id = self._selected_id()
        if sig_id is None:
            return
        name = self._name.text().strip()
        body = self._body.text().replace("\\n", "\n")
        session = get_session()
        update_signature(session, sig_id, name=name, body=body)
        session.close()
        self._load()

    def _delete(self):
        sig_id = self._selected_id()
        if sig_id is None:
            return
        session = get_session()
        delete_signature(session, sig_id)
        session.close()
        self._load()

    def _set_default(self):
        sig_id = self._selected_id()
        if sig_id is None:
            return
        session = get_session()
        set_default(session, sig_id)
        session.close()
        self._load()


class _PositionWidget(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        self._table = QTableWidget(0, 2)
        self._table.setHorizontalHeaderLabels(["役職名", "表示順"])
        self._table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.currentRowChanged.connect(self._on_select)
        layout.addWidget(self._table)

        form = QFormLayout()
        self._name = QLineEdit()
        self._sort_order = QSpinBox()
        self._sort_order.setRange(0, 9999)
        form.addRow("役職名", self._name)
        form.addRow("表示順", self._sort_order)
        layout.addLayout(form)

        btn_row = QHBoxLayout()
        btn_add = QPushButton("追加")
        btn_add.clicked.connect(self._add)
        btn_update = QPushButton("更新")
        btn_update.clicked.connect(self._update)
        btn_delete = QPushButton("削除")
        btn_delete.clicked.connect(self._delete)
        btn_row.addWidget(btn_add)
        btn_row.addWidget(btn_update)
        btn_row.addWidget(btn_delete)
        btn_row.addStretch()
        layout.addLayout(btn_row)
        self._load()

    def _load(self):
        session = get_session()
        try:
            self._positions = get_positions(session)
        finally:
            session.close()
        self._table.setRowCount(0)
        for p in self._positions:
            row = self._table.rowCount()
            self._table.insertRow(row)
            self._table.setItem(row, 0, QTableWidgetItem(p.name))
            self._table.setItem(row, 1, QTableWidgetItem(str(p.sort_order)))
            self._table.item(row, 0).setData(Qt.ItemDataRole.UserRole, p.id)

    def _on_select(self, row: int):
        if row < 0 or row >= len(self._positions):
            return
        p = self._positions[row]
        self._name.setText(p.name)
        self._sort_order.setValue(p.sort_order)

    def _selected_id(self) -> int | None:
        row = self._table.currentRow()
        if row < 0:
            return None
        return self._table.item(row, 0).data(Qt.ItemDataRole.UserRole)

    def _add(self):
        name = self._name.text().strip()
        if not name:
            return
        session = get_session()
        create_position(session, name, self._sort_order.value())
        session.close()
        self._load()

    def _update(self):
        pos_id = self._selected_id()
        if pos_id is None:
            return
        session = get_session()
        update_position(session, pos_id, name=self._name.text().strip(),
                        sort_order=self._sort_order.value())
        session.close()
        self._load()

    def _delete(self):
        pos_id = self._selected_id()
        if pos_id is None:
            return
        session = get_session()
        delete_position(session, pos_id)
        session.close()
        self._load()


class _StaffWidget(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        self._table = QTableWidget(0, 2)
        self._table.setHorizontalHeaderLabels(["職員名", "有効"])
        self._table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self._table)

        form = QFormLayout()
        self._name = QLineEdit()
        form.addRow("職員名", self._name)
        layout.addLayout(form)

        btn_row = QHBoxLayout()
        btn_add = QPushButton("追加")
        btn_add.clicked.connect(self._add)
        btn_toggle = QPushButton("有効/無効切り替え")
        btn_toggle.clicked.connect(self._toggle)
        btn_row.addWidget(btn_add)
        btn_row.addWidget(btn_toggle)
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
            self._table.item(row, 0).setData(Qt.ItemDataRole.UserRole, s.id)

    def _add(self):
        name = self._name.text().strip()
        if not name:
            return
        session = get_session()
        create_staff(session, name)
        session.close()
        self._name.clear()
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
```

- [ ] **Step 2: 全テスト確認**

```bash
pytest tests/ -v
```

期待: 全テストがパス

- [ ] **Step 3: コミット**

```bash
git add app/ui/settings_tab.py
git commit -m "feat: 設定タブ（Graph API設定・署名・役職・職員管理）を実装 — Plan 3完了"
```

---

## Plan 3 完了チェックリスト

- [ ] `pytest tests/ -v` で全テストがパス
- [ ] テンプレートタブでテンプレートを追加・編集・削除できる
- [ ] 設定タブ → Microsoft 365 でテナントID等を保存・接続テストできる
- [ ] 設定タブ → 署名管理でデフォルト署名を設定できる
- [ ] 設定タブ → 会議所役職で役職を追加・並び替えできる
- [ ] 設定タブ → 職員管理で職員を追加・有効/無効切り替えできる
