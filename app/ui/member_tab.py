# app/ui/member_tab.py
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLineEdit, QComboBox, QLabel, QHeaderView,
    QMessageBox, QCheckBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
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
        self._show_inactive = QCheckBox("議員退任者を含む")
        self._show_inactive.stateChanged.connect(self._load)
        btn_add     = QPushButton("追加")
        btn_edit    = QPushButton("編集")
        btn_delete  = QPushButton("議員退任")
        btn_history = QPushButton("変更履歴")
        btn_import  = QPushButton("インポート")
        btn_order   = QPushButton("順番設定")
        btn_add.clicked.connect(self._add)
        btn_edit.clicked.connect(self._edit)
        btn_delete.clicked.connect(self._delete)
        btn_history.clicked.connect(self._show_history)
        btn_import.clicked.connect(self._import)
        btn_order.clicked.connect(self._order_settings)
        toolbar.addWidget(self._search, 2)
        toolbar.addWidget(QLabel("役職:"))
        toolbar.addWidget(self._pos_filter)
        toolbar.addWidget(self._show_inactive)
        toolbar.addStretch()
        toolbar.addWidget(btn_add)
        toolbar.addWidget(btn_edit)
        toolbar.addWidget(btn_delete)
        toolbar.addWidget(btn_history)
        toolbar.addWidget(btn_import)
        toolbar.addWidget(btn_order)
        layout.addLayout(toolbar)

        # 一覧テーブル
        self._table = QTableWidget(0, 13)
        self._table.setHorizontalHeaderLabels([
            "会員番号", "会議所役職", "事業所名", "事業所名フリガナ",
            "氏名", "氏名フリガナ", "役職名",
            "メール1", "メール2", "メール3", "メール4", "メール5",
            "最終更新日",
        ])
        self._table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.Interactive)
        self._table.setColumnWidth(2, 200)
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
            if current is not None:
                for i in range(self._pos_filter.count()):
                    if self._pos_filter.itemData(i) == current:
                        self._pos_filter.setCurrentIndex(i)
                        break
            self._pos_filter.blockSignals(False)
        finally:
            session.close()

    def _load(self):
        self._load_positions()
        active_only = not self._show_inactive.isChecked()
        session = get_session()
        try:
            members = get_members(
                session,
                position_id=self._pos_filter.currentData(),
                keyword=self._search.text().strip() or None,
                active_only=active_only,
            )
            self._members = members
            self._table.setRowCount(0)
            gray = QColor("#9CA3AF")
            for m in members:
                row = self._table.rowCount()
                self._table.insertRow(row)
                is_retired = not m.is_active
                pos_name = m.position.name if m.position else ""
                values = [
                    m.member_number,
                    pos_name,
                    m.organization_name,
                    m.organization_kana or "",
                    m.name,
                    m.name_kana or "",
                    m.title or "",
                ]
                for col, val in enumerate(values):
                    item = QTableWidgetItem(val)
                    if is_retired:
                        item.setForeground(gray)
                    self._table.setItem(row, col, item)
                for ei, ea in enumerate(m.email_addresses[:5]):
                    label = f"（{ea.label}）" if ea.label else ""
                    item = QTableWidgetItem(f"{ea.address}{label}")
                    if is_retired:
                        item.setForeground(gray)
                    self._table.setItem(row, 7 + ei, item)
                upd = m.updated_at.strftime("%Y/%m/%d") if m.updated_at else ""
                item = QTableWidgetItem(upd)
                if is_retired:
                    item.setForeground(gray)
                self._table.setItem(row, 12, item)
                self._table.item(row, 0).setData(Qt.ItemDataRole.UserRole, m.id)
                self._table.item(row, 0).setData(Qt.ItemDataRole.UserRole + 1,
                                                  m.is_active)
            active_count = sum(1 for m in members if m.is_active)
            if active_only:
                self._count_label.setText(f"{len(members)} 件")
            else:
                retired_count = len(members) - active_count
                self._count_label.setText(
                    f"{active_count} 件（議員退任者 {retired_count} 件を含む）")
        finally:
            session.close()

    def _selected_member_id(self) -> int | None:
        row = self._table.currentRow()
        if row < 0:
            return None
        item = self._table.item(row, 0)
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def _selected_is_active(self) -> bool:
        row = self._table.currentRow()
        if row < 0:
            return False
        item = self._table.item(row, 0)
        if item is None:
            return False
        val = item.data(Qt.ItemDataRole.UserRole + 1)
        return bool(val)

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
        if not self._selected_is_active():
            QMessageBox.information(self, "議員退任済み", "この会員はすでに議員退任処理済みです。")
            return
        ret = QMessageBox.question(
            self, "議員退任処理確認",
            "この会員を議員退任処理しますか？\n一覧から非表示になりますが、変更履歴は保持されます。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if ret != QMessageBox.StandardButton.Yes:
            return
        session = get_session()
        delete_member(session, member_id, changed_by=self._staff_name)
        session.close()
        self._show_inactive.setChecked(True)  # 退任者を含む表示に切り替え
        # _load() は setChecked によって自動的に呼ばれる
        # 退任した行を選択状態に戻す
        for r in range(self._table.rowCount()):
            item = self._table.item(r, 0)
            if item and item.data(Qt.ItemDataRole.UserRole) == member_id:
                self._table.selectRow(r)
                break
        QMessageBox.information(self, "議員退任完了",
                                "議員退任処理が完了しました。\n変更履歴ボタンで履歴を確認できます。")

    def _show_history(self):
        member_id = self._selected_member_id()
        if member_id is None:
            QMessageBox.information(self, "選択なし", "会員を選択してください。")
            return
        from app.ui.dialogs.member_history_dialog import MemberHistoryDialog
        session = get_session()
        dlg = MemberHistoryDialog(session, member_id, parent=self)
        dlg.exec()
        session.close()

    def _order_settings(self):
        from app.ui.dialogs.order_settings_dialog import OrderSettingsDialog
        session = get_session()
        dlg = OrderSettingsDialog(session, parent=self)
        if dlg.exec():
            self._load()
        session.close()

    def _import(self):
        from app.ui.dialogs.import_dialog import ImportDialog
        session = get_session()
        dlg = ImportDialog(session, staff_name=self._staff_name, parent=self)
        if dlg.exec():
            self._load()
        session.close()
