# 委員会管理・委員会別メール送信 実装計画

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 会員が最大1つ所属する「委員会」（総務・運営委員会／地域経済推進委員会／中小・小規模企業委員会）を新しい属性として管理し、委員会ごとに絞り込んでメールを送信できるようにする。

**Architecture:** 既存の`Position`（会議所役職）の実装パターンを完全に踏襲する。新規テーブル`Committee`＋`Member.committee_id`を追加し、サービス層・設定タブ・会員編集ダイアログ・名簿タブ・送信タブ・インポート/エクスポートの各層に同型の変更を積み重ねる。

**Tech Stack:** Python 3.11+, PyQt6, SQLAlchemy, pytest, pytest-qt

**Spec:** `docs/superpowers/specs/2026-07-10-committee-management-design.md`

## Global Constraints

- ウィンドウ初期サイズは780×728px以内に収めること（`C:\Users\taka\.claude\CLAUDE.md`の全プロジェクト共通ルール）。本機能は既存タブ内への追加のみのため、新規ウィンドウ／ダイアログは作成しない。
- 既存の命名規則・ディレクトリ構成・実装パターン（`get_session()`の都度生成、`QMessageBox`の使い方、`Position`関連コードの構造）を踏襲する。
- 会員は委員会に最大1つまで所属（複数所属なし）。
- 委員会マスタの並び替えUIは作らない（3件程度のため、追加順の`sort_order`自動採番で十分）。
- 各タスクは独立して実装・テスト・コミット可能。Task 1・2は他の全タスクの前提となるため最初に実施する。Task 3〜8はTask 1・2完了後、任意の順で実施可能。
- テストは`tests/conftest.py`の`db_session`フィクスチャ、またはpytest-qtの`qtbot`フィクスチャを使う。実DB（`get_session()`）へのアクセスが発生するUIコードは`monkeypatch`でサービス関数・`get_session`を差し替える。

---

## Task 1: Committeeモデル追加とDBマイグレーション

**Files:**
- Modify: `app/database/models.py:13-19`（`Position`直後）, `app/database/models.py:22-51`（`Member`）
- Modify: `app/database/connection.py:16-67`（`_migrate_sqlite`）, `app/database/connection.py:69-77`（`_migrate_postgresql`）
- Test: `tests/test_committee_model.py`（新規）

**Interfaces:**
- Produces: `Committee`モデル（`id`, `name`, `sort_order`, `members`）、`Member.committee_id`、`Member.committee`

- [ ] **Step 1: 失敗するテストを書く**

```python
# tests/test_committee_model.py
from app.database.models import Committee, Member


def test_committee_model_fields(db_session):
    c = Committee(name="総務・運営委員会", sort_order=1)
    db_session.add(c)
    db_session.commit()
    assert c.id is not None


def test_member_committee_relationship(db_session):
    c = Committee(name="地域経済推進委員会", sort_order=2)
    db_session.add(c)
    db_session.commit()

    m = Member(member_number="A-001", organization_name="テスト商事",
               name="山田太郎", committee_id=c.id)
    db_session.add(m)
    db_session.commit()

    assert m.committee.name == "地域経済推進委員会"
    assert m in c.members
```

- [ ] **Step 2: テストを実行して失敗を確認**

Run: `pytest tests/test_committee_model.py -v`
Expected: FAIL — `ImportError: cannot import name 'Committee' from 'app.database.models'`

- [ ] **Step 3: `Committee`モデルと`Member`への関連付けを実装**

`app/database/models.py:13-19`（`Position`クラス）の直後に追加:

```python
class Committee(Base):
    __tablename__ = "committees"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    sort_order = Column(Integer, nullable=False, default=0)

    members = relationship("Member", back_populates="committee")
```

`app/database/models.py`の`Member`クラス内、`position_id`カラムの直後に追加:

```python
    position_id = Column(Integer, ForeignKey("positions.id"), nullable=True)
    committee_id = Column(Integer, ForeignKey("committees.id"), nullable=True)
```

`Member`クラス内、`position`リレーションの直後に追加:

```python
    position = relationship("Position", back_populates="members")
    committee = relationship("Committee", back_populates="members")
```

- [ ] **Step 4: テストを実行して成功を確認**

Run: `pytest tests/test_committee_model.py -v`
Expected: PASS

- [ ] **Step 5: 既存DBへのマイグレーション処理を追加**

`app/database/connection.py`の`_migrate_sqlite`関数内、既存の`photo_full`カラム追加処理の直後に追加:

```python
        members_cols = {
            row[1] for row in conn.execute(text("PRAGMA table_info(members)"))
        }
        if "committee_id" not in members_cols:
            conn.execute(text(
                "ALTER TABLE members ADD COLUMN committee_id INTEGER"
            ))
            conn.commit()
```

`app/database/connection.py`の`_migrate_postgresql`関数内、既存の`photo_full`カラム追加処理の直後に追加:

```python
        if "committee_id" not in members_cols:
            conn.execute(text("ALTER TABLE members ADD COLUMN committee_id INTEGER"))
```

（新規テーブル`committees`は`Base.metadata.create_all()`で自動生成されるため、マイグレーション処理は不要）

- [ ] **Step 6: コミット**

```bash
git add app/database/models.py app/database/connection.py tests/test_committee_model.py
git commit -m "feat: Committeeモデルを追加しMemberに委員会を関連付ける"
```

---

## Task 2: committee_service.py

**Files:**
- Create: `app/services/committee_service.py`
- Test: `tests/test_committee_service.py`（新規）

**Interfaces:**
- Consumes: `Committee`モデル（Task 1）
- Produces: `create_committee(session, name, sort_order) -> Committee`, `get_committees(session) -> list[Committee]`, `update_committee(session, committee_id, **kwargs) -> Committee`, `delete_committee(session, committee_id) -> None`

- [ ] **Step 1: 失敗するテストを書く**

```python
# tests/test_committee_service.py
from app.services.committee_service import (
    create_committee, get_committees, update_committee, delete_committee
)


def test_create_and_get_committees(db_session):
    create_committee(db_session, "総務・運営委員会", 1)
    create_committee(db_session, "地域経済推進委員会", 2)
    committees = get_committees(db_session)
    assert [c.name for c in committees] == ["総務・運営委員会", "地域経済推進委員会"]


def test_get_committees_ordered_by_sort_order(db_session):
    create_committee(db_session, "中小・小規模企業委員会", 2)
    create_committee(db_session, "総務・運営委員会", 1)
    committees = get_committees(db_session)
    assert [c.name for c in committees] == ["総務・運営委員会", "中小・小規模企業委員会"]


def test_update_committee(db_session):
    c = create_committee(db_session, "旧名称", 1)
    update_committee(db_session, c.id, name="新名称")
    committees = get_committees(db_session)
    assert committees[0].name == "新名称"


def test_delete_committee(db_session):
    c = create_committee(db_session, "削除対象", 1)
    delete_committee(db_session, c.id)
    assert get_committees(db_session) == []
```

- [ ] **Step 2: テストを実行して失敗を確認**

Run: `pytest tests/test_committee_service.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.committee_service'`

- [ ] **Step 3: `committee_service.py`を実装**

```python
# app/services/committee_service.py
from sqlalchemy.orm import Session
from app.database.models import Committee


def create_committee(session: Session, name: str, sort_order: int) -> Committee:
    committee = Committee(name=name, sort_order=sort_order)
    session.add(committee)
    session.commit()
    return committee


def get_committees(session: Session) -> list[Committee]:
    return session.query(Committee).order_by(Committee.sort_order).all()


def update_committee(session: Session, committee_id: int, **kwargs) -> Committee:
    committee = session.get(Committee, committee_id)
    if committee is None:
        raise ValueError(f"委員会ID {committee_id} が見つかりません")
    for k, v in kwargs.items():
        setattr(committee, k, v)
    session.commit()
    return committee


def delete_committee(session: Session, committee_id: int) -> None:
    committee = session.get(Committee, committee_id)
    if committee:
        session.delete(committee)
        session.commit()
```

- [ ] **Step 4: テストを実行して成功を確認**

Run: `pytest tests/test_committee_service.py -v`
Expected: PASS

- [ ] **Step 5: コミット**

```bash
git add app/services/committee_service.py tests/test_committee_service.py
git commit -m "feat: 委員会CRUDサービスを追加"
```

---

## Task 3: 会員編集ダイアログに委員会コンボを追加

**Files:**
- Modify: `app/ui/dialogs/member_edit_dialog.py`
- Test: `tests/test_member_edit_dialog_committee.py`（新規）

**Interfaces:**
- Consumes: `get_committees(session)`（Task 2）, `_NoWheelComboBox`（既存クラス、`app/ui/dialogs/member_edit_dialog.py:17-21`）
- Produces: `MemberEditDialog._committee_combo`（`QComboBox`、`currentData()`で選択中の`committee_id`を返す）

- [ ] **Step 1: 失敗するテストを書く**

```python
# tests/test_member_edit_dialog_committee.py
from PyQt6.QtCore import QPoint, QPointF, Qt
from PyQt6.QtGui import QWheelEvent
from app.services.committee_service import create_committee


def test_committee_combo_populated_and_saved(qtbot, db_session):
    c1 = create_committee(db_session, "総務・運営委員会", 1)
    create_committee(db_session, "地域経済推進委員会", 2)

    from app.ui.dialogs.member_edit_dialog import MemberEditDialog
    dlg = MemberEditDialog(db_session, staff_name="担当者A")
    qtbot.addWidget(dlg)

    assert dlg._committee_combo.count() == 3  # （なし）+ 2委員会

    for i in range(dlg._committee_combo.count()):
        if dlg._committee_combo.itemData(i) == c1.id:
            dlg._committee_combo.setCurrentIndex(i)
            break

    dlg._member_number.setText("A-100")
    dlg._org_name.setText("テスト商事")
    dlg._name.setText("山田太郎")
    dlg._save()

    from app.services.member_service import get_members
    saved = next(m for m in get_members(db_session) if m.member_number == "A-100")
    assert saved.committee_id == c1.id


def test_committee_combo_ignores_wheel_scroll(qtbot, db_session):
    from app.ui.dialogs.member_edit_dialog import MemberEditDialog
    dlg = MemberEditDialog(db_session, staff_name="担当者A")
    qtbot.addWidget(dlg)

    before = dlg._committee_combo.currentIndex()
    event = QWheelEvent(
        QPointF(10, 10), QPointF(10, 10),
        QPoint(0, 0), QPoint(0, 120),
        Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.NoScrollPhase, False,
    )
    dlg._committee_combo.wheelEvent(event)
    assert dlg._committee_combo.currentIndex() == before
```

- [ ] **Step 2: テストを実行して失敗を確認**

Run: `pytest tests/test_member_edit_dialog_committee.py -v`
Expected: FAIL — `AttributeError: 'MemberEditDialog' object has no attribute '_committee_combo'`

- [ ] **Step 3: 委員会コンボを実装**

`app/ui/dialogs/member_edit_dialog.py`のimport部分を置き換える:

```python
from app.database.models import Member, Position
from app.services.member_service import (
    create_member, update_member, set_email_addresses, record_member_history
)
from app.services.committee_service import get_committees
```

`_build`内、`self._position_combo = _NoWheelComboBox()`の直後（`self._notes = QLineEdit()`の前）に追加:

```python
        self._position_combo = _NoWheelComboBox()
        self._committee_combo = _NoWheelComboBox()
        self._notes = QLineEdit()
```

`self._positions`の読み込み直後に追加:

```python
        self._positions = self._session.query(Position).order_by(Position.sort_order).all()
        self._position_combo.addItem("（なし）", None)
        for p in self._positions:
            self._position_combo.addItem(p.name, p.id)

        self._committees = get_committees(self._session)
        self._committee_combo.addItem("（なし）", None)
        for c in self._committees:
            self._committee_combo.addItem(c.name, c.id)
```

`form.addRow("会議所役職", self._position_combo)`の直後に追加:

```python
        form.addRow("会議所役職", self._position_combo)
        form.addRow("委員会", self._committee_combo)
```

`_load`メソッド内、役職の選択復元処理の直後に追加:

```python
        for i, p in enumerate(self._positions):
            if p.id == member.position_id:
                self._position_combo.setCurrentIndex(i + 1)
                break
        for i, c in enumerate(self._committees):
            if c.id == member.committee_id:
                self._committee_combo.setCurrentIndex(i + 1)
                break
```

`_save`メソッド内、`position_id = self._position_combo.currentData()`の直後に追加:

```python
        position_id = self._position_combo.currentData()
        committee_id = self._committee_combo.currentData()
```

`_save`内の`update_member(...)`呼び出しの`position_id=position_id,`の直後に追加:

```python
                    position_id=position_id,
                    committee_id=committee_id,
                )
                set_email_addresses(self._session, self._member.id, addresses)
```

`_save`内の`create_member(...)`呼び出しの`position_id=position_id,`の直後に追加:

```python
                    position_id=position_id,
                    committee_id=committee_id,
                )
                set_email_addresses(self._session, m.id, addresses)
```

`_current_state`メソッドを置き換える:

```python
    def _current_state(self) -> tuple:
        emails = tuple(
            (a.text().strip(), l.text().strip()) for a, l in self._email_rows)
        return (
            self._member_number.text().strip(),
            self._org_name.text().strip(),
            self._org_kana.text().strip(),
            self._title.text().strip(),
            self._name.text().strip(),
            self._name_kana.text().strip(),
            self._notes.text().strip(),
            self._position_combo.currentData(),
            self._committee_combo.currentData(),
            emails,
        )
```

- [ ] **Step 4: テストを実行して成功を確認**

Run: `pytest tests/test_member_edit_dialog_committee.py -v`
Expected: PASS

- [ ] **Step 5: 既存テストに影響がないことを確認**

Run: `pytest tests/test_member_edit_dialog_unsaved.py -v`
Expected: PASS（`_current_state`の変更がタプル比較の未保存検知ロジックに影響しないことを確認）

- [ ] **Step 6: コミット**

```bash
git add app/ui/dialogs/member_edit_dialog.py tests/test_member_edit_dialog_committee.py
git commit -m "feat: 会員編集ダイアログに委員会選択を追加"
```

---

## Task 4: 名簿タブに委員会列を追加

**Files:**
- Modify: `app/ui/member_tab.py:100-138`（`_build`のテーブル部分）, `app/ui/member_tab.py:169-249`（`_load`）
- Modify: `app/services/member_service.py:65-88`（`get_members`、N+1回避のためeager load追加）
- Test: `tests/test_member_tab_committee_column.py`（新規）

**Interfaces:**
- Consumes: `Member.committee`（Task 1）

- [ ] **Step 1: 失敗するテストを書く**

```python
# tests/test_member_tab_committee_column.py
def test_member_tab_shows_committee_column(qtbot, monkeypatch):
    class _Committee:
        name = "総務・運営委員会"

    class _Member:
        def __init__(self):
            self.id = 1
            self.member_number = "A-001"
            self.organization_name = "テスト商事"
            self.organization_kana = ""
            self.name = "山田太郎"
            self.name_kana = ""
            self.title = ""
            self.position = None
            self.committee = _Committee()
            self.email_addresses = []
            self.is_active = True
            self.updated_at = None
            self.photo_thumb = None

    class _FakeSession:
        def close(self):
            pass

    monkeypatch.setattr("app.ui.member_tab.get_session", lambda: _FakeSession())
    monkeypatch.setattr("app.ui.member_tab.get_members", lambda *a, **k: [_Member()])

    from app.ui.member_tab import MemberTab
    tab = MemberTab()
    qtbot.addWidget(tab)

    assert tab._table.columnCount() == 11
    assert tab._table.horizontalHeaderItem(3).text() == "委員会"
    assert tab._table.item(0, 3).text() == "総務・運営委員会"
```

- [ ] **Step 2: テストを実行して失敗を確認**

Run: `pytest tests/test_member_tab_committee_column.py -v`
Expected: FAIL — `assert 10 == 11`

- [ ] **Step 3: 委員会列を追加**

`app/ui/member_tab.py`の`_build`内、テーブル構築部分を置き換える:

```python
        # 一覧テーブル
        self._table = QTableWidget(0, 11)
        self._table.setHorizontalHeaderLabels([
            "写真",
            "会員番号", "会議所役職", "委員会", "事業所名", "事業所名フリガナ",
            "氏名", "氏名フリガナ", "役職名",
            "メール(件数)", "最終更新日",
        ])
        self._table.horizontalHeader().setSectionResizeMode(
            4, QHeaderView.ResizeMode.Interactive)
        self._table.setColumnWidth(0, 44)
        self._table.setColumnWidth(4, 200)
```

`_load`内、テキスト列の構築部分を置き換える:

```python
                committee_name = m.committee.name if m.committee else ""

                # Cols 1-8: テキスト（旧 0-7）
                values = [
                    m.member_number,
                    pos_name,
                    committee_name,
                    m.organization_name,
                    m.organization_kana or "",
                    m.name,
                    m.name_kana or "",
                    m.title or "",
                ]
                for i, val in enumerate(values):
                    item = QTableWidgetItem(val)
                    if is_retired:
                        item.setForeground(gray)
                    self._table.setItem(row, i + 1, item)

                # Col 9: メール件数（詳細は編集画面で確認）
                item = QTableWidgetItem(f"{len(m.email_addresses)}件")
                if is_retired:
                    item.setForeground(gray)
                self._table.setItem(row, 9, item)

                # Col 10: 最終更新日
                upd = m.updated_at.strftime("%Y/%m/%d") if m.updated_at else ""
                item = QTableWidgetItem(upd)
                if is_retired:
                    item.setForeground(gray)
                self._table.setItem(row, 10, item)
```

`app/services/member_service.py`の`get_members`内、クエリオプションを置き換える（N+1クエリを避けるため`Member.committee`をeager load対象に追加）:

```python
    q = (session.query(Member)
         .outerjoin(Member.position)
         .options(contains_eager(Member.position),
                  selectinload(Member.committee),
                  selectinload(Member.email_addresses)))
```

- [ ] **Step 4: テストを実行して成功を確認**

Run: `pytest tests/test_member_tab_committee_column.py -v`
Expected: PASS

- [ ] **Step 5: 既存テストに影響がないことを確認**

Run: `pytest tests/test_member_tab_toolbar_buttons.py tests/test_tab_refresh.py -v`
Expected: PASS（列インデックスのずれが選択状態・ボタン有効化ロジックに影響しないことを確認。これらのテストは列2以降の値を直接検証していないため影響なし）

- [ ] **Step 6: コミット**

```bash
git add app/ui/member_tab.py app/services/member_service.py tests/test_member_tab_committee_column.py
git commit -m "feat: 名簿タブの一覧に委員会列を追加"
```

---

## Task 5: 設定タブに委員会管理を追加

**Files:**
- Modify: `app/ui/settings_tab.py`
- Test: `tests/test_settings_committee_widget.py`（新規）

**Interfaces:**
- Consumes: `get_committees`, `create_committee`, `update_committee`, `delete_committee`（Task 2）

- [ ] **Step 1: 失敗するテストを書く**

```python
# tests/test_settings_committee_widget.py
from PyQt6.QtWidgets import QMessageBox
from app.services.committee_service import get_committees


def test_add_update_delete_committee(qtbot, monkeypatch, db_session):
    monkeypatch.setattr("app.ui.settings_tab.get_session", lambda: db_session)
    monkeypatch.setattr(
        QMessageBox, "question",
        staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes))

    from app.ui.settings_tab import _CommitteeWidget
    w = _CommitteeWidget()
    qtbot.addWidget(w)

    w._name.setText("総務・運営委員会")
    w._add()
    assert w._table.rowCount() == 1
    assert w._table.item(0, 0).text() == "総務・運営委員会"

    w._table.selectRow(0)
    w._name.setText("総務・運営委員会（改）")
    w._update()
    assert w._table.item(0, 0).text() == "総務・運営委員会（改）"

    w._table.selectRow(0)
    w._delete()
    assert w._table.rowCount() == 0
    assert get_committees(db_session) == []
```

- [ ] **Step 2: テストを実行して失敗を確認**

Run: `pytest tests/test_settings_committee_widget.py -v`
Expected: FAIL — `ImportError: cannot import name '_CommitteeWidget'`

- [ ] **Step 3: `_CommitteeWidget`を実装しタブに登録**

`app/ui/settings_tab.py`のimport部分に追加:

```python
from app.services.committee_service import (
    get_committees, create_committee, update_committee, delete_committee
)
from app.database.models import Member
```

`SettingsTab.__init__`内、タブ登録部分に追加:

```python
        inner.addTab(_GraphSettingsWidget(), "Microsoft 365")
        inner.addTab(_SignatureWidget(), "署名管理")
        inner.addTab(_CommitteeWidget(), "委員会管理")
        inner.addTab(_StaffWidget(), "職員管理")
```

ファイル末尾（既存クラス定義の後）に`_CommitteeWidget`を追加:

```python
class _CommitteeWidget(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        self._table = QTableWidget(0, 1)
        self._table.setHorizontalHeaderLabels(["委員会名"])
        self._table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.itemSelectionChanged.connect(self._on_select)
        layout.addWidget(self._table)

        form = QFormLayout()
        self._name = QLineEdit()
        form.addRow("委員会名", self._name)
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
        layout.addStretch()
        self._load()

    def _load(self):
        session = get_session()
        try:
            self._committees = get_committees(session)
        finally:
            session.close()
        self._table.setRowCount(0)
        for c in self._committees:
            row = self._table.rowCount()
            self._table.insertRow(row)
            self._table.setItem(row, 0, QTableWidgetItem(c.name))
            self._table.item(row, 0).setData(Qt.ItemDataRole.UserRole, c.id)

    def _on_select(self):
        row = self._table.currentRow()
        if row < 0 or row >= len(self._committees):
            return
        self._name.setText(self._committees[row].name)

    def _selected_id(self) -> int | None:
        row = self._table.currentRow()
        if row < 0:
            return None
        return self._table.item(row, 0).data(Qt.ItemDataRole.UserRole)

    def _add(self):
        name = self._name.text().strip()
        if not name:
            QMessageBox.warning(self, "入力エラー", "委員会名を入力してください。")
            return
        session = get_session()
        next_order = len(self._committees) + 1
        create_committee(session, name, next_order)
        session.close()
        self._name.clear()
        self._load()

    def _update(self):
        committee_id = self._selected_id()
        if committee_id is None:
            return
        name = self._name.text().strip()
        if not name:
            QMessageBox.warning(self, "入力エラー", "委員会名を入力してください。")
            return
        session = get_session()
        update_committee(session, committee_id, name=name)
        session.close()
        self._load()

    def _delete(self):
        committee_id = self._selected_id()
        if committee_id is None:
            return
        session = get_session()
        try:
            member_count = (
                session.query(Member)
                .filter_by(committee_id=committee_id, is_active=True)
                .count()
            )
        finally:
            session.close()
        if member_count:
            msg = (f"この委員会には現在 {member_count} 件の会員が所属しています。\n"
                   "削除すると所属設定が解除されます。削除しますか？")
        else:
            msg = "この委員会を削除しますか？"
        ret = QMessageBox.question(
            self, "削除確認", msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if ret != QMessageBox.StandardButton.Yes:
            return
        session = get_session()
        try:
            session.query(Member).filter_by(committee_id=committee_id).update(
                {"committee_id": None})
            session.commit()
            delete_committee(session, committee_id)
        finally:
            session.close()
        self._name.clear()
        self._load()
```

- [ ] **Step 4: テストを実行して成功を確認**

Run: `pytest tests/test_settings_committee_widget.py -v`
Expected: PASS

- [ ] **Step 5: コミット**

```bash
git add app/ui/settings_tab.py tests/test_settings_committee_widget.py
git commit -m "feat: 設定タブに委員会管理を追加"
```

---

## Task 6: 送信タブに「委員会で選ぶ」モードを追加

**Files:**
- Modify: `app/ui/send_tab.py`
- Test: `tests/test_send_tab_committee_filter.py`（新規）

**Interfaces:**
- Consumes: `get_committees(session)`（Task 2）, `Member.committee_id`（Task 1）
- Produces: `SendTab._rb_by_committee`, `SendTab._committee_list`, `SendTab._on_committee_select()`

- [ ] **Step 1: 失敗するテストを書く**

```python
# tests/test_send_tab_committee_filter.py
class _Member:
    def __init__(self, id, committee_id):
        self.id = id
        self.member_number = f"A-{id:03d}"
        self.organization_name = f"org{id}"
        self.organization_kana = ""
        self.name = "テスト太郎"
        self.name_kana = ""
        self.title = ""
        self.position = None
        self.position_id = None
        self.committee_id = committee_id
        self.email_addresses = []


class _Committee:
    def __init__(self, id, name):
        self.id = id
        self.name = name


class _FakeSession:
    def close(self):
        pass


def test_committee_filter_checks_only_matching_members(qtbot, monkeypatch):
    committees = [_Committee(1, "総務・運営委員会"), _Committee(2, "地域経済推進委員会")]
    members = [_Member(1, committee_id=1), _Member(2, committee_id=2),
               _Member(3, committee_id=None)]

    monkeypatch.setattr("app.ui.send_tab.get_session", lambda: _FakeSession())
    monkeypatch.setattr("app.ui.send_tab.get_positions", lambda s: [])
    monkeypatch.setattr("app.ui.send_tab.get_committees", lambda s: committees)
    monkeypatch.setattr("app.ui.send_tab.get_members", lambda s: members)
    monkeypatch.setattr("app.ui.send_tab.get_templates", lambda s: [])
    monkeypatch.setattr("app.ui.send_tab.get_signatures", lambda s: [])
    monkeypatch.setattr("app.ui.send_tab.get_default_signature", lambda s: None)

    from app.ui.send_tab import SendTab
    tab = SendTab(staff_name="担当者A")
    qtbot.addWidget(tab)

    tab._rb_by_committee.setChecked(True)
    tab._committee_list.setCurrentRow(0)  # 総務・運営委員会を選択

    selected = tab._recipient.get_selected_members()
    assert [m.id for m in selected] == [1]
```

- [ ] **Step 2: テストを実行して失敗を確認**

Run: `pytest tests/test_send_tab_committee_filter.py -v`
Expected: FAIL — `AttributeError: 'SendTab' object has no attribute '_rb_by_committee'`

- [ ] **Step 3: 「委員会で選ぶ」モードを実装**

`app/ui/send_tab.py`のimport部分に追加:

```python
from app.services.position_service import get_positions
from app.services.committee_service import get_committees
```

`_build_step1`メソッドを置き換える:

```python
    def _build_step1(self) -> QGroupBox:
        grp = QGroupBox("Step 1：宛先条件")
        layout = QVBoxLayout(grp)

        mode_row = QHBoxLayout()
        self._rb_by_pos = QRadioButton("役職で選ぶ")
        self._rb_by_committee = QRadioButton("委員会で選ぶ")
        self._rb_by_attend = QRadioButton("会議の出欠で選ぶ")
        self._rb_by_pos.setChecked(True)
        bg = QButtonGroup(self)
        bg.addButton(self._rb_by_pos)
        bg.addButton(self._rb_by_committee)
        bg.addButton(self._rb_by_attend)
        self._rb_by_pos.toggled.connect(self._on_mode_change)
        self._rb_by_committee.toggled.connect(self._on_mode_change)
        mode_row.addWidget(self._rb_by_pos)
        mode_row.addWidget(self._rb_by_committee)
        mode_row.addWidget(self._rb_by_attend)
        mode_row.addStretch()
        layout.addLayout(mode_row)

        self._pos_panel = QWidget()
        pp = QVBoxLayout(self._pos_panel)
        pp.setContentsMargins(0, 0, 0, 0)
        pp.addWidget(QLabel("会議所役職（複数選択可 / Ctrl+クリック）："))
        self._pos_list = QListWidget()
        self._pos_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        self._pos_list.setMaximumHeight(100)
        self._pos_list.itemSelectionChanged.connect(self._on_pos_select)
        pp.addWidget(self._pos_list)
        layout.addWidget(self._pos_panel)

        self._committee_panel = QWidget()
        cp = QVBoxLayout(self._committee_panel)
        cp.setContentsMargins(0, 0, 0, 0)
        cp.addWidget(QLabel("委員会（複数選択可 / Ctrl+クリック）："))
        self._committee_list = QListWidget()
        self._committee_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        self._committee_list.setMaximumHeight(100)
        self._committee_list.itemSelectionChanged.connect(self._on_committee_select)
        cp.addWidget(self._committee_list)
        self._committee_panel.setVisible(False)
        layout.addWidget(self._committee_panel)

        self._attend_panel = QWidget()
        ap = QVBoxLayout(self._attend_panel)
        ap.setContentsMargins(0, 0, 0, 0)
        mrow = QHBoxLayout()
        mrow.addWidget(QLabel("会議:"))
        self._meeting_combo = QComboBox()
        self._meeting_combo.currentIndexChanged.connect(self._on_attend_filter)
        mrow.addWidget(self._meeting_combo, 1)
        ap.addLayout(mrow)
        srow = QHBoxLayout()
        srow.addWidget(QLabel("対象:"))
        self._status_checks: dict[str, QCheckBox] = {}
        for s in ["未回答", "欠席", "出席", "委任", "代理"]:
            cb = QCheckBox(s)
            cb.stateChanged.connect(self._on_attend_filter)
            srow.addWidget(cb)
            self._status_checks[s] = cb
        srow.addStretch()
        ap.addLayout(srow)
        self._attend_panel.setVisible(False)
        layout.addWidget(self._attend_panel)

        return grp
```

`_load_combos`内、役職リスト読み込みの直後に追加:

```python
            self._pos_list.blockSignals(False)

            self._committee_list.blockSignals(True)
            self._committee_list.clear()
            for c in get_committees(session):
                item = QListWidgetItem(c.name)
                item.setData(Qt.ItemDataRole.UserRole, c.id)
                self._committee_list.addItem(item)
            self._committee_list.blockSignals(False)

            self._members = get_members(session)
```

`_clear_all`メソッド内、`self._pos_list.clearSelection()`の直後に追加:

```python
        self._pos_list.clearSelection()
        self._committee_list.clearSelection()
```

`_on_mode_change`メソッドを置き換える:

```python
    def _on_mode_change(self):
        is_pos = self._rb_by_pos.isChecked()
        is_committee = self._rb_by_committee.isChecked()
        is_attend = self._rb_by_attend.isChecked()
        self._pos_panel.setVisible(is_pos)
        self._committee_panel.setVisible(is_committee)
        self._attend_panel.setVisible(is_attend)
        if is_attend:
            self._load_meeting_combo()
        self._recipient.clear_checks()
```

`_on_pos_select`メソッドの直後に追加:

```python
    def _on_committee_select(self):
        selected_committee_ids = {
            item.data(Qt.ItemDataRole.UserRole)
            for item in self._committee_list.selectedItems()
        }
        if not selected_committee_ids:
            self._recipient.clear_checks()
            return
        member_ids = {m.id for m in self._members
                     if m.committee_id in selected_committee_ids}
        self._recipient.set_checks_by_member_ids(member_ids)
```

- [ ] **Step 4: テストを実行して成功を確認**

Run: `pytest tests/test_send_tab_committee_filter.py -v`
Expected: PASS

- [ ] **Step 5: コミット**

```bash
git add app/ui/send_tab.py tests/test_send_tab_committee_filter.py
git commit -m "feat: 送信タブに委員会で絞り込むモードを追加"
```

---

## Task 7: 名簿インポートに委員会列を対応

**Files:**
- Modify: `app/services/import_service.py`
- Modify: `app/ui/dialogs/import_dialog.py:10-28`（`_MEMBER_FIELDS`）, `app/ui/dialogs/import_dialog.py:130-147`（`auto_map`）
- Test: `tests/test_import_committee.py`（新規）

**Interfaces:**
- Consumes: `Committee`モデル（Task 1）

- [ ] **Step 1: 失敗するテストを書く**

```python
# tests/test_import_committee.py
from app.services.import_service import import_members
from app.services.committee_service import get_committees, create_committee
from app.services.member_service import get_members


def test_import_creates_new_committee_from_name(db_session):
    rows = [["A-001", "テスト商事", "山田太郎", "総務・運営委員会"]]
    column_map = {
        "member_number": 0, "organization_name": 1,
        "name": 2, "committee_name": 3,
    }
    result = import_members(db_session, rows, column_map, changed_by="担当者A")
    assert result["created"] == 1

    committees = get_committees(db_session)
    assert [c.name for c in committees] == ["総務・運営委員会"]

    member = get_members(db_session)[0]
    assert member.committee_id == committees[0].id


def test_import_maps_to_existing_committee(db_session):
    c = create_committee(db_session, "地域経済推進委員会", 1)
    rows = [["A-002", "テスト工業", "鈴木花子", "地域経済推進委員会"]]
    column_map = {
        "member_number": 0, "organization_name": 1,
        "name": 2, "committee_name": 3,
    }
    import_members(db_session, rows, column_map, changed_by="担当者A")

    assert len(get_committees(db_session)) == 1  # 新規作成されない
    member = get_members(db_session)[0]
    assert member.committee_id == c.id
```

- [ ] **Step 2: テストを実行して失敗を確認**

Run: `pytest tests/test_import_committee.py -v`
Expected: FAIL — `member.committee_id`が`None`のまま（`committee_name`列マッピングが未実装のため）

- [ ] **Step 3: インポート処理と列マッピングUIに委員会を追加**

`app/services/import_service.py`のimport部分を置き換える:

```python
from app.database.models import Position, Committee, MemberHistory
```

`import_members`関数内、`position_map`の定義直後に追加:

```python
    position_map = {p.name: p.id for p in session.query(Position).all()}
    committee_map = {c.name: c.id for c in session.query(Committee).all()}
```

`position_name`の処理ブロックの直後に追加:

```python
        if "position_name" in column_map:
            position_name = _cell(row, "position_name")
            if position_name:
                if position_name not in position_map:
                    new_pos = Position(name=position_name, sort_order=0)
                    session.add(new_pos)
                    session.flush()
                    position_map[position_name] = new_pos.id
                kwargs["position_id"] = position_map[position_name]
            else:
                kwargs["position_id"] = None

        if "committee_name" in column_map:
            committee_name = _cell(row, "committee_name")
            if committee_name:
                if committee_name not in committee_map:
                    new_committee = Committee(name=committee_name, sort_order=0)
                    session.add(new_committee)
                    session.flush()
                    committee_map[committee_name] = new_committee.id
                kwargs["committee_id"] = committee_map[committee_name]
            else:
                kwargs["committee_id"] = None
```

`app/ui/dialogs/import_dialog.py`の`_MEMBER_FIELDS`内、`position_name`の行の直後に追加:

```python
    ("position_name",    "会議所役職"),
    ("committee_name",   "委員会"),
```

`_populate_combos`内の`auto_map`辞書に追加:

```python
            "会議所役職": "position_name",
            "会議所役職名": "position_name",
            "委員会": "committee_name",
            "所属委員会": "committee_name",
        }
```

- [ ] **Step 4: テストを実行して成功を確認**

Run: `pytest tests/test_import_committee.py -v`
Expected: PASS

- [ ] **Step 5: 既存のインポートテストに影響がないことを確認**

Run: `pytest tests/ -k import -v`
Expected: PASS

- [ ] **Step 6: コミット**

```bash
git add app/services/import_service.py app/ui/dialogs/import_dialog.py tests/test_import_committee.py
git commit -m "feat: 名簿インポートに委員会列を対応"
```

---

## Task 8: 名簿エクスポートに委員会列を対応

**Files:**
- Modify: `app/services/export_service.py`
- Test: `tests/test_export_committee.py`（新規）

**Interfaces:**
- Consumes: `Member.committee`（Task 1）

- [ ] **Step 1: 失敗するテストを書く**

```python
# tests/test_export_committee.py
from app.services.committee_service import create_committee
from app.services.member_service import create_member
from app.services.export_service import export_members_csv


def test_export_csv_includes_committee_column(db_session, tmp_path):
    c = create_committee(db_session, "中小・小規模企業委員会", 1)
    create_member(db_session, "A-001", "テスト商事", "山田太郎", committee_id=c.id)
    db_session.commit()

    path = tmp_path / "out.csv"
    count = export_members_csv(db_session, str(path))
    assert count == 1

    content = path.read_text(encoding="utf-8-sig")
    assert "委員会" in content
    assert "中小・小規模企業委員会" in content
```

- [ ] **Step 2: テストを実行して失敗を確認**

Run: `pytest tests/test_export_committee.py -v`
Expected: FAIL — `assert "委員会" in content`（出力に委員会列がまだない）

- [ ] **Step 3: エクスポート列に委員会を追加**

`app/services/export_service.py`の`_HEADERS`を置き換える:

```python
_HEADERS = [
    "会員番号", "事業所名", "事業所名フリガナ", "役職名", "氏名", "氏名フリガナ", "会議所役職", "委員会",
    "メール1アドレス", "メール1ラベル",
    "メール2アドレス", "メール2ラベル",
    "メール3アドレス", "メール3ラベル",
    "メール4アドレス", "メール4ラベル",
    "メール5アドレス", "メール5ラベル",
]
```

`_build_row`関数内、`row`リストの定義を置き換える:

```python
    row = [
        member.member_number,
        member.organization_name,
        member.organization_kana or "",
        member.title or "",
        member.name,
        member.name_kana or "",
        member.position.name if member.position else "",
        member.committee.name if member.committee else "",
    ]
```

- [ ] **Step 4: テストを実行して成功を確認**

Run: `pytest tests/test_export_committee.py -v`
Expected: PASS

- [ ] **Step 5: コミット**

```bash
git add app/services/export_service.py tests/test_export_committee.py
git commit -m "feat: 名簿エクスポートに委員会列を対応"
```

---

## 完了後の確認

- [ ] **全テストスイートを実行**

Run: `pytest -q`
Expected: 全件PASS

- [ ] **アプリを起動して手動確認**

以下を実機（PyQt6アプリ）で確認する:
1. 設定タブ→「委員会管理」で3委員会（総務・運営委員会／地域経済推進委員会／中小・小規模企業委員会）を登録
2. 名簿タブで会員を数件編集し、委員会を設定→一覧に委員会列が表示される
3. 送信タブでStep 1「委員会で選ぶ」を選択→委員会を選ぶと宛先一覧が絞り込まれる
4. 名簿のエクスポート→委員会列が出力される
5. 名簿のインポート（委員会列を含むExcel）→委員会が自動作成・マッピングされる
