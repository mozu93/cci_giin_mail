# cci-mail Plan 1: 基盤（Foundation）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** プロジェクト初期化・全DBモデル・設定管理・メインウィンドウ骨格（タブあり、各タブは空）を構築し、`python main.py` でウィンドウが起動する状態にする。

**Architecture:** SQLAlchemy + SQLite（WALモード）でDBを管理。設定はJSON（app_config.json）で読み書き。PyQt6でタブ型メインウィンドウを構築。各タブは後続プランで実装するため、ここではQWidgetのプレースホルダーとして作成する。

**Tech Stack:** Python 3.11+, PyQt6, SQLAlchemy 2.x, SQLite, pytest

## Global Constraints

- Python 3.11+、PyQt6、SQLAlchemy 2.x を使用
- ウィンドウ初期サイズ：780×728px 以内
- 共有フォルダ運用のためSQLiteはWALモードを有効化（PRAGMA journal_mode=WAL）
- 外部キー制約を有効化（PRAGMA foreign_keys=ON）
- 設定ファイル（app_config.json）とDB（cci_mail.db）はmain.pyと同じディレクトリに置く
- テストはインメモリSQLiteを使用

---

## ファイル構成（新規作成）

```
cci-mail/
  main.py
  start.bat
  requirements.txt
  requirements-dev.txt
  pytest.ini
  app/
    __init__.py
    database/
      __init__.py
      models.py
      connection.py
    services/
      __init__.py
    ui/
      __init__.py
      main_window.py
      member_tab.py        # プレースホルダー（空のQWidget）
      template_tab.py      # プレースホルダー
      send_tab.py          # プレースホルダー
      history_tab.py       # プレースホルダー
      settings_tab.py      # プレースホルダー
      dialogs/
        __init__.py
    utils/
      __init__.py
      app_config.py
  tests/
    __init__.py
    conftest.py
    test_models.py
    test_app_config.py
```

---

## Task 1: プロジェクト初期化

**Files:**
- Create: `requirements.txt`
- Create: `requirements-dev.txt`
- Create: `pytest.ini`
- Create: `app/__init__.py`
- Create: `app/database/__init__.py`
- Create: `app/services/__init__.py`
- Create: `app/ui/__init__.py`
- Create: `app/ui/dialogs/__init__.py`
- Create: `app/utils/__init__.py`
- Create: `tests/__init__.py`

**Interfaces:**
- Produces: インストール可能な依存関係一覧、pytest設定

- [ ] **Step 1: requirements.txt を作成**

```
PyQt6>=6.6.0
SQLAlchemy>=2.0.0
openpyxl>=3.1.0
requests>=2.31.0
msal>=1.26.0
```

- [ ] **Step 2: requirements-dev.txt を作成**

```
pytest>=8.0.0
pytest-qt>=4.4.0
```

- [ ] **Step 3: pytest.ini を作成**

```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
```

- [ ] **Step 4: 全 `__init__.py` を作成（空ファイル）**

以下のパスすべてに空の `__init__.py` を作成する：
- `app/__init__.py`
- `app/database/__init__.py`
- `app/services/__init__.py`
- `app/ui/__init__.py`
- `app/ui/dialogs/__init__.py`
- `app/utils/__init__.py`
- `tests/__init__.py`

- [ ] **Step 5: 依存パッケージをインストール**

```bash
pip install -r requirements.txt -r requirements-dev.txt
```

期待出力: `Successfully installed ...`

- [ ] **Step 6: コミット**

```bash
git init
git add requirements.txt requirements-dev.txt pytest.ini app/ tests/
git commit -m "chore: プロジェクト初期化"
```

---

## Task 2: DBモデル

**Files:**
- Create: `app/database/models.py`
- Create: `tests/conftest.py`
- Create: `tests/test_models.py`

**Interfaces:**
- Produces:
  - `Position(name: str, sort_order: int)`
  - `Member(member_number: str, organization_name: str, name: str, ...)`
  - `EmailAddress(member_id: int, address: str, label: str, sort_order: int)`
  - `MemberHistory(member_id: int, changed_by: str, change_reason: str, snapshot: str)`
  - `Signature(name: str, body: str, is_default: bool)`
  - `EmailTemplate(name: str, subject: str, body: str, signature_id: int|None)`
  - `Staff(name: str, is_active: bool)`
  - `SendJob(name: str, template_id: int, staff_id: int, status: str, ...)`
  - `SendLog(job_id: int, member_id: int, to_address: str, subject: str, status: str, ...)`
  - `Base` （全モデルの基底クラス）

- [ ] **Step 1: テストのfixture（conftest.py）を作成**

```python
# tests/conftest.py
import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from app.database.models import Base


def _enable_fk(dbapi_conn, connection_record):
    dbapi_conn.execute("PRAGMA foreign_keys=ON")


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    event.listen(engine, "connect", _enable_fk)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    Base.metadata.drop_all(engine)
```

- [ ] **Step 2: テストを書く**

```python
# tests/test_models.py
import json
from app.database.models import (
    Position, Member, EmailAddress, MemberHistory,
    Signature, EmailTemplate, Staff, SendJob, SendLog
)


def test_create_position(db_session):
    pos = Position(name="会頭", sort_order=1)
    db_session.add(pos)
    db_session.commit()
    assert pos.id is not None
    assert pos.name == "会頭"


def test_create_member_with_emails(db_session):
    pos = Position(name="議員", sort_order=10)
    db_session.add(pos)
    db_session.flush()
    member = Member(
        member_number="A-001",
        position_id=pos.id,
        organization_name="○○商事",
        organization_kana="マルマルショウジ",
        title="代表取締役",
        name="山田 太郎",
        name_kana="ヤマダ タロウ",
    )
    db_session.add(member)
    db_session.flush()
    email1 = EmailAddress(member_id=member.id, address="yamada@example.com",
                          label="本人", sort_order=1)
    email2 = EmailAddress(member_id=member.id, address="somu@example.com",
                          label="総務", sort_order=2)
    db_session.add_all([email1, email2])
    db_session.commit()
    fetched = db_session.get(Member, member.id)
    assert fetched.organization_name == "○○商事"
    assert len(fetched.email_addresses) == 2
    assert fetched.email_addresses[0].address == "yamada@example.com"


def test_member_history_snapshot(db_session):
    member = Member(member_number="B-001", organization_name="△△産業", name="鈴木 花子")
    db_session.add(member)
    db_session.flush()
    snapshot = json.dumps(
        {"organization_name": "△△産業", "name": "鈴木 花子", "email_addresses": []},
        ensure_ascii=False
    )
    history = MemberHistory(
        member_id=member.id,
        changed_by="田中",
        change_reason="住所変更",
        snapshot=snapshot,
    )
    db_session.add(history)
    db_session.commit()
    fetched = db_session.get(Member, member.id)
    assert len(fetched.history) == 1
    assert fetched.history[0].change_reason == "住所変更"
    loaded = json.loads(fetched.history[0].snapshot)
    assert loaded["organization_name"] == "△△産業"


def test_template_with_signature(db_session):
    sig = Signature(name="標準署名", body="商工会議所\n担当：田中", is_default=True)
    db_session.add(sig)
    db_session.flush()
    tmpl = EmailTemplate(name="総会案内", subject="総会のご案内",
                         body="本文テスト", signature_id=sig.id)
    db_session.add(tmpl)
    db_session.commit()
    fetched = db_session.get(EmailTemplate, tmpl.id)
    assert fetched.signature.name == "標準署名"


def test_send_job_with_logs(db_session):
    staff = Staff(name="田中")
    template = EmailTemplate(name="総会案内", subject="総会のご案内", body="本文")
    db_session.add_all([staff, template])
    db_session.flush()
    job = SendJob(
        name="2026年6月 総会案内",
        template_id=template.id,
        staff_id=staff.id,
        status="done",
        total_count=2,
        success_count=1,
        error_count=1,
    )
    db_session.add(job)
    db_session.flush()
    log1 = SendLog(job_id=job.id, to_address="a@example.com",
                   subject="総会のご案内", status="success")
    log2 = SendLog(job_id=job.id, to_address="b@example.com",
                   subject="総会のご案内", status="error",
                   error_message="接続タイムアウト")
    db_session.add_all([log1, log2])
    db_session.commit()
    fetched = db_session.get(SendJob, job.id)
    assert len(fetched.logs) == 2
    error_logs = [l for l in fetched.logs if l.status == "error"]
    assert error_logs[0].error_message == "接続タイムアウト"


def test_email_address_cascade_delete(db_session):
    member = Member(member_number="C-001", organization_name="□□工業", name="佐藤 次郎")
    db_session.add(member)
    db_session.flush()
    email = EmailAddress(member_id=member.id, address="sato@example.com",
                         label="本人", sort_order=1)
    db_session.add(email)
    db_session.commit()
    db_session.delete(member)
    db_session.commit()
    remaining = db_session.query(EmailAddress).filter_by(member_id=member.id).all()
    assert len(remaining) == 0
```

- [ ] **Step 3: テスト実行 → 失敗確認**

```bash
pytest tests/test_models.py -v
```

期待: `ImportError: cannot import name 'Position' from 'app.database.models'`

- [ ] **Step 4: models.py を作成**

```python
# app/database/models.py
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, Text, ForeignKey
)
from sqlalchemy.orm import relationship, DeclarativeBase


class Base(DeclarativeBase):
    pass


class Position(Base):
    __tablename__ = "positions"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    sort_order = Column(Integer, nullable=False, default=0)

    members = relationship("Member", back_populates="position")


class Member(Base):
    __tablename__ = "members"
    id = Column(Integer, primary_key=True)
    member_number = Column(String, unique=True, nullable=False)
    position_id = Column(Integer, ForeignKey("positions.id"), nullable=True)
    organization_name = Column(String, nullable=False)
    organization_kana = Column(String, default="")
    title = Column(String, default="")
    name = Column(String, nullable=False)
    name_kana = Column(String, default="")
    notes = Column(Text, default="")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.now)
    updated_at = Column(DateTime, nullable=False,
                        default=datetime.now, onupdate=datetime.now)

    position = relationship("Position", back_populates="members")
    email_addresses = relationship(
        "EmailAddress", back_populates="member",
        order_by="EmailAddress.sort_order",
        cascade="all, delete-orphan"
    )
    history = relationship(
        "MemberHistory", back_populates="member",
        order_by="MemberHistory.changed_at.desc()",
        cascade="all, delete-orphan"
    )


class EmailAddress(Base):
    __tablename__ = "email_addresses"
    id = Column(Integer, primary_key=True)
    member_id = Column(Integer, ForeignKey("members.id"), nullable=False)
    address = Column(String, nullable=False)
    label = Column(String, default="")
    sort_order = Column(Integer, nullable=False, default=1)

    member = relationship("Member", back_populates="email_addresses")


class MemberHistory(Base):
    __tablename__ = "member_history"
    id = Column(Integer, primary_key=True)
    member_id = Column(Integer, ForeignKey("members.id"), nullable=False)
    changed_at = Column(DateTime, nullable=False, default=datetime.now)
    changed_by = Column(String, nullable=False)
    change_reason = Column(String, nullable=False)
    snapshot = Column(Text, nullable=False)  # JSON: members全フィールド＋email_addresses配列

    member = relationship("Member", back_populates="history")


class Signature(Base):
    __tablename__ = "signatures"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    body = Column(Text, nullable=False)
    is_default = Column(Boolean, default=False)

    templates = relationship("EmailTemplate", back_populates="signature")


class EmailTemplate(Base):
    __tablename__ = "email_templates"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    subject = Column(String, nullable=False)
    body = Column(Text, nullable=False)
    signature_id = Column(Integer, ForeignKey("signatures.id"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.now)
    updated_at = Column(DateTime, nullable=False,
                        default=datetime.now, onupdate=datetime.now)

    signature = relationship("Signature", back_populates="templates")


class Staff(Base):
    __tablename__ = "staff"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)

    send_jobs = relationship("SendJob", back_populates="staff")


class SendJob(Base):
    __tablename__ = "send_jobs"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    template_id = Column(Integer, ForeignKey("email_templates.id"), nullable=True)
    staff_id = Column(Integer, ForeignKey("staff.id"), nullable=True)
    status = Column(String, nullable=False, default="draft")
    total_count = Column(Integer, default=0)
    success_count = Column(Integer, default=0)
    error_count = Column(Integer, default=0)
    created_at = Column(DateTime, nullable=False, default=datetime.now)
    sent_at = Column(DateTime, nullable=True)

    template = relationship("EmailTemplate")
    staff = relationship("Staff", back_populates="send_jobs")
    logs = relationship("SendLog", back_populates="job", cascade="all, delete-orphan")


class SendLog(Base):
    __tablename__ = "send_logs"
    id = Column(Integer, primary_key=True)
    job_id = Column(Integer, ForeignKey("send_jobs.id"), nullable=False)
    member_id = Column(Integer, ForeignKey("members.id"), nullable=True)
    to_address = Column(String, nullable=False)
    subject = Column(String, nullable=False)
    status = Column(String, nullable=False)  # success / error / skip
    error_message = Column(Text, default="")
    sent_at = Column(DateTime, nullable=True)

    job = relationship("SendJob", back_populates="logs")
    member = relationship("Member")
```

- [ ] **Step 5: テスト実行 → パス確認**

```bash
pytest tests/test_models.py -v
```

期待: `6 passed`

- [ ] **Step 6: コミット**

```bash
git add app/database/models.py tests/conftest.py tests/test_models.py
git commit -m "feat: 全DBモデルを定義"
```

---

## Task 3: DB接続管理

**Files:**
- Create: `app/database/connection.py`

**Interfaces:**
- Consumes: `Base`（models.py）、`get_db_path()`（app_config.py — Task 4で実装。ここでは後回し可）
- Produces:
  - `get_engine() -> Engine`
  - `get_session() -> Session`

- [ ] **Step 1: connection.py を作成**

```python
# app/database/connection.py
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from app.database.models import Base

_engine = None
_SessionLocal = None


def _configure_sqlite(dbapi_conn, connection_record):
    dbapi_conn.execute("PRAGMA journal_mode=WAL")
    dbapi_conn.execute("PRAGMA foreign_keys=ON")


def get_engine(db_path: str | None = None):
    global _engine
    if _engine is None:
        if db_path is None:
            from app.utils.app_config import get_db_path
            db_path = get_db_path()
        _engine = create_engine(f"sqlite:///{db_path}", echo=False)
        event.listen(_engine, "connect", _configure_sqlite)
        Base.metadata.create_all(_engine)
    return _engine


def get_session() -> Session:
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=get_engine())
    return _SessionLocal()


def reset_engine() -> None:
    """テスト用：エンジンをリセットする"""
    global _engine, _SessionLocal
    _engine = None
    _SessionLocal = None
```

- [ ] **Step 2: コミット**

```bash
git add app/database/connection.py
git commit -m "feat: DBセッション管理（WALモード）を追加"
```

---

## Task 4: アプリ設定管理

**Files:**
- Create: `app/utils/app_config.py`
- Create: `tests/test_app_config.py`

**Interfaces:**
- Produces:
  - `get_config() -> dict`
  - `save_config(config: dict) -> None`
  - `get_db_path() -> str`
  - `get_graph_config() -> dict`

- [ ] **Step 1: テストを書く**

```python
# tests/test_app_config.py
import json
import pytest
from pathlib import Path


@pytest.fixture
def tmp_config(tmp_path, monkeypatch):
    config_file = tmp_path / "app_config.json"
    monkeypatch.setattr("app.utils.app_config._CONFIG_DIR",
                        lambda: tmp_path)
    return config_file


def test_get_config_returns_empty_when_no_file(tmp_path, monkeypatch):
    monkeypatch.setattr("app.utils.app_config._CONFIG_DIR",
                        lambda: tmp_path)
    from app.utils import app_config
    # モジュールを再インポートして設定パスを上書き
    import importlib
    importlib.reload(app_config)
    result = app_config.get_config()
    assert result == {}


def test_save_and_load_config(tmp_path, monkeypatch):
    import importlib
    from app.utils import app_config
    monkeypatch.setattr(app_config, "_config_path",
                        lambda: tmp_path / "app_config.json")
    importlib.reload(app_config)

    app_config.save_config({"key": "value"})
    result = app_config.get_config()
    assert result["key"] == "value"


def test_get_graph_config(tmp_path, monkeypatch):
    import importlib
    from app.utils import app_config
    monkeypatch.setattr(app_config, "_config_path",
                        lambda: tmp_path / "app_config.json")

    app_config.save_config({
        "graph": {
            "tenant_id": "xxx-tenant",
            "client_id": "xxx-client",
            "client_secret": "xxx-secret",
            "from_address": "noreply@example.com",
        }
    })
    cfg = app_config.get_graph_config()
    assert cfg["tenant_id"] == "xxx-tenant"
    assert cfg["from_address"] == "noreply@example.com"
```

- [ ] **Step 2: テスト実行 → 失敗確認**

```bash
pytest tests/test_app_config.py -v
```

期待: `ImportError` または `ModuleNotFoundError`

- [ ] **Step 3: app_config.py を作成**

```python
# app/utils/app_config.py
import json
from pathlib import Path


def _config_path() -> Path:
    return Path(__file__).parent.parent.parent / "app_config.json"


def _db_default_path() -> Path:
    return Path(__file__).parent.parent.parent / "cci_mail.db"


def get_config() -> dict:
    p = _config_path()
    if p.exists():
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_config(config: dict) -> None:
    p = _config_path()
    with open(p, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def get_db_path() -> str:
    config = get_config()
    db_path = config.get("db_path", "")
    if db_path:
        return db_path
    return str(_db_default_path())


def get_graph_config() -> dict:
    return get_config().get("graph", {})
```

- [ ] **Step 4: テスト実行 → パス確認**

```bash
pytest tests/test_app_config.py -v
```

期待: `3 passed`

- [ ] **Step 5: コミット**

```bash
git add app/utils/app_config.py tests/test_app_config.py
git commit -m "feat: アプリ設定管理（JSON読み書き・Graph API設定・DBパス）を追加"
```

---

## Task 5: メインウィンドウ骨格 + プレースホルダータブ

**Files:**
- Create: `main.py`
- Create: `start.bat`
- Create: `app/ui/main_window.py`
- Create: `app/ui/member_tab.py`
- Create: `app/ui/template_tab.py`
- Create: `app/ui/send_tab.py`
- Create: `app/ui/history_tab.py`
- Create: `app/ui/settings_tab.py`

**Interfaces:**
- Consumes: なし（後続プランが各タブを置き換える）
- Produces: `python main.py` でウィンドウが起動し、5つのタブが表示される

- [ ] **Step 1: 各タブのプレースホルダーを作成**

各ファイルに同じパターンで作成する（ファイルごとにラベルのみ変える）：

```python
# app/ui/member_tab.py
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel


class MemberTab(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("名簿管理（実装予定）"))
```

```python
# app/ui/template_tab.py
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel


class TemplateTab(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("テンプレート管理（実装予定）"))
```

```python
# app/ui/send_tab.py
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel


class SendTab(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("メール送信（実装予定）"))
```

```python
# app/ui/history_tab.py
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel


class HistoryTab(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("送信履歴（実装予定）"))
```

```python
# app/ui/settings_tab.py
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel


class SettingsTab(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("設定（実装予定）"))
```

- [ ] **Step 2: main_window.py を作成**

```python
# app/ui/main_window.py
from PyQt6.QtWidgets import QMainWindow, QTabWidget
from app.ui.member_tab import MemberTab
from app.ui.template_tab import TemplateTab
from app.ui.send_tab import SendTab
from app.ui.history_tab import HistoryTab
from app.ui.settings_tab import SettingsTab


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("商工会議所メール配信システム")
        self.resize(780, 728)
        self._build_tabs()

    def _build_tabs(self):
        tabs = QTabWidget()
        self.setCentralWidget(tabs)
        tabs.addTab(MemberTab(), "名簿管理")
        tabs.addTab(TemplateTab(), "テンプレート")
        tabs.addTab(SendTab(), "メール送信")
        tabs.addTab(HistoryTab(), "送信履歴")
        tabs.addTab(SettingsTab(), "設定")
```

- [ ] **Step 3: main.py を作成**

```python
# main.py
import sys
from PyQt6.QtWidgets import QApplication
from app.ui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("cci-mail")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: start.bat を作成**

```bat
@echo off
cd /d "%~dp0"
python main.py
pause
```

- [ ] **Step 5: 起動確認**

```bash
python main.py
```

期待: ウィンドウが開き、5タブ（名簿管理・テンプレート・メール送信・送信履歴・設定）が表示される。各タブに「〜（実装予定）」のラベルが表示される。

- [ ] **Step 6: 全テスト確認**

```bash
pytest tests/ -v
```

期待: `9 passed`（test_models: 6件 + test_app_config: 3件）

- [ ] **Step 7: コミット**

```bash
git add main.py start.bat app/ui/
git commit -m "feat: メインウィンドウ骨格（5タブ）を追加 — Plan 1完了"
```

---

## Plan 1 完了チェックリスト

- [ ] `pip install -r requirements.txt -r requirements-dev.txt` が成功する
- [ ] `pytest tests/ -v` で `9 passed`
- [ ] `python main.py` でウィンドウが起動し、5タブが表示される
- [ ] ウィンドウサイズが 780×728px 以内に収まっている
- [ ] `cci_mail.db` が自動生成される（起動後）
