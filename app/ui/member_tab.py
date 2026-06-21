# app/ui/member_tab.py
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLineEdit, QComboBox, QLabel, QHeaderView,
    QMessageBox
)
from PyQt6.QtCore import Qt
from app.database.connection import get_session
from app.database.models import Position
from app.services.member_service import get_members, delete_member


class MemberTab(QWidget):
    def __init__(self):
        super().__init__()
        self._staff_name = ""
        self._build()
        self._load()

    def set_staff_name(self, name: str):
        self._staff_name = name

    def _build(self):
        layout = QVBoxLayout(self)

        # ツールバー
        toolbar = QHBoxLayout()
        self._search = QLineEdit()
        self._search.setPlaceholderText("キーワード検索（事業所名・氏名・会員番号）")
        self._search.textChanged.connect(self._load)
        self._pos_filter = QComboBox()
        self._pos_filter.addItem("すべての役職", None)
        self._pos_filter.currentIndexChanged.connect(self._load)
        btn_add = QPushButton("追加")
        btn_add.clicked.connect(self._add)
        btn_edit = QPushButton("編集")
        btn_edit.clicked.connect(self._edit)
        btn_delete = QPushButton("削除")
        btn_delete.clicked.connect(self._delete)
        btn_history = QPushButton("変更履歴")
        btn_history.clicked.connect(self._show_history)
        btn_import = QPushButton("インポート")
        btn_import.clicked.connect(self._import)
        toolbar.addWidget(self._search, 2)
        toolbar.addWidget(QLabel("役職:"))
        toolbar.addWidget(self._pos_filter)
        toolbar.addStretch()
        toolbar.addWidget(btn_add)
        toolbar.addWidget(btn_edit)
        toolbar.addWidget(btn_delete)
        toolbar.addWidget(btn_history)
        toolbar.addWidget(btn_import)
        layout.addLayout(toolbar)

        # 一覧テーブル
        self._table = QTableWidget(0, 12)
        self._table.setHorizontalHeaderLabels([
            "会員番号", "会議所役職", "事業所名", "事業所名フリガナ",
            "氏名", "氏名フリガナ", "役職名",
            "メール1", "メール2", "メール3", "メール4", "メール5",
        ])
        self._table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.Stretch)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.doubleClicked.connect(self._edit)
        layout.addWidget(self._table)

        self._count_label = QLabel("")
        layout.addWidget(self._count_label)

    def _load_positions(self):
        session = get_session()
        try:
            positions = session.query(Position).order_by(Position.sort_order).all()
            current = self._pos_filter.currentData()
            self._pos_filter.blockSignals(True)
            self._pos_filter.clear()
            self._pos_filter.addItem("すべての役職", None)
            for p in positions:
                self._pos_filter.addItem(p.name, p.id)
            self._pos_filter.blockSignals(False)
            if current is not None:
                for i in range(self._pos_filter.count()):
                    if self._pos_filter.itemData(i) == current:
                        self._pos_filter.setCurrentIndex(i)
                        break
        finally:
            session.close()

    def _load(self):
        self._load_positions()
        session = get_session()
        try:
            members = get_members(
                session,
                position_id=self._pos_filter.currentData(),
                keyword=self._search.text().strip() or None,
            )
            self._members = members
            self._table.setRowCount(0)
            for m in members:
                row = self._table.rowCount()
                self._table.insertRow(row)
                self._table.setItem(row, 0, QTableWidgetItem(m.member_number))
                pos_name = m.position.name if m.position else ""
                self._table.setItem(row, 1, QTableWidgetItem(pos_name))
                self._table.setItem(row, 2, QTableWidgetItem(m.organization_name))
                self._table.setItem(row, 3, QTableWidgetItem(m.organization_kana or ""))
                self._table.setItem(row, 4, QTableWidgetItem(m.name))
                self._table.setItem(row, 5, QTableWidgetItem(m.name_kana or ""))
                self._table.setItem(row, 6, QTableWidgetItem(m.title or ""))
                for ei, ea in enumerate(m.email_addresses[:5]):
                    label = f"（{ea.label}）" if ea.label else ""
                    self._table.setItem(row, 7 + ei, QTableWidgetItem(f"{ea.address}{label}"))
                self._table.item(row, 0).setData(
                    Qt.ItemDataRole.UserRole, m.id)
            self._count_label.setText(f"{len(members)} 件")
        finally:
            session.close()

    def _selected_member_id(self) -> int | None:
        row = self._table.currentRow()
        if row < 0:
            return None
        item = self._table.item(row, 0)
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def _add(self):
        from app.ui.dialogs.member_edit_dialog import MemberEditDialog
        session = get_session()
        dlg = MemberEditDialog(session, staff_name=self._staff_name, parent=self)
        if dlg.exec():
            self._load()
        session.close()

    def _edit(self):
        member_id = self._selected_member_id()
        if member_id is None:
            return
        from app.ui.dialogs.member_edit_dialog import MemberEditDialog
        from app.services.member_service import get_member
        session = get_session()
        member = get_member(session, member_id)
        dlg = MemberEditDialog(session, member=member,
                               staff_name=self._staff_name, parent=self)
        if dlg.exec():
            self._load()
        session.close()

    def _delete(self):
        member_id = self._selected_member_id()
        if member_id is None:
            return
        ret = QMessageBox.question(
            self, "削除確認",
            "この会員を削除しますか？\n関連する変更履歴もすべて削除されます。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if ret != QMessageBox.StandardButton.Yes:
            return
        session = get_session()
        delete_member(session, member_id)
        session.close()
        self._load()

    def _show_history(self):
        member_id = self._selected_member_id()
        if member_id is None:
            return
        from app.ui.dialogs.member_history_dialog import MemberHistoryDialog
        session = get_session()
        dlg = MemberHistoryDialog(session, member_id, parent=self)
        dlg.exec()
        session.close()

    def _import(self):
        from app.ui.dialogs.import_dialog import ImportDialog
        session = get_session()
        dlg = ImportDialog(session, staff_name=self._staff_name, parent=self)
        if dlg.exec():
            self._load()
        session.close()
