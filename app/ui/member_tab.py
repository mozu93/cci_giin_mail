# app/ui/member_tab.py
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLineEdit, QComboBox, QLabel, QHeaderView,
    QMessageBox, QCheckBox, QMenu
)
from PyQt6.QtCore import Qt, QPoint
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

    def showEvent(self, event):
        """Update empty hint visibility when widget is shown."""
        super().showEvent(event)
        self._update_empty_hint_visibility()

    def _update_empty_hint_visibility(self):
        """Update the visibility of the empty hint label."""
        if not hasattr(self, '_members'):
            return
        no_filter = (
            not self._search.text().strip()
            and self._pos_filter.currentData() is None
            and not self._show_inactive.isChecked()
        )
        # Ensure all parents are visible so isVisible() returns True
        parent = self._empty_hint.parent()
        while parent:
            if not parent.isVisible():
                parent.setVisible(True)
            parent = parent.parent()
        self._empty_hint.setVisible(no_filter and len(self._members) == 0)

    def refresh(self):
        self._load()

    def set_staff_name(self, name: str):
        self._staff_name = name

    def _build(self):
        layout = QVBoxLayout(self)

        # ツールバー 1行目：検索・フィルター
        row1 = QHBoxLayout()
        self._search = QLineEdit()
        self._search.setPlaceholderText("キーワード検索（事業所名・氏名・会員番号）")
        self._search.textChanged.connect(self._load)
        self._pos_filter = QComboBox()
        self._pos_filter.addItem("すべての役職", None)
        self._pos_filter.currentIndexChanged.connect(self._load)
        self._show_inactive = QCheckBox("議員退任者を含む")
        self._show_inactive.stateChanged.connect(self._load)
        row1.addWidget(self._search, 2)
        row1.addWidget(QLabel("役職:"))
        row1.addWidget(self._pos_filter)
        row1.addWidget(self._show_inactive)
        row1.addStretch()
        layout.addLayout(row1)

        # ツールバー 2行目：操作ボタン
        row2 = QHBoxLayout()
        btn_add = QPushButton("追加")
        btn_add.clicked.connect(self._add)

        self._btn_edit = QPushButton("編集")
        self._btn_edit.setEnabled(False)
        self._btn_edit.clicked.connect(self._edit)
        self._btn_history = QPushButton("変更履歴")
        self._btn_history.setEnabled(False)
        self._btn_history.clicked.connect(self._show_history)
        self._btn_retire = QPushButton("議員退任")
        self._btn_retire.setEnabled(False)
        self._btn_retire.clicked.connect(self._delete)

        btn_file = QPushButton("ファイル")
        file_menu = QMenu(btn_file)
        file_menu.addAction("インポート", self._import)
        file_menu.addAction("インポート取り消し", self._import_revert)
        file_menu.addSeparator()
        file_menu.addAction("エクスポート", self._export)
        btn_file.setMenu(file_menu)

        btn_order = QPushButton("順番設定")
        btn_order.clicked.connect(self._order_settings)

        row2.addWidget(btn_add)
        row2.addWidget(self._btn_edit)
        row2.addWidget(self._btn_history)
        row2.addWidget(self._btn_retire)
        row2.addWidget(btn_file)
        row2.addWidget(btn_order)
        row2.addStretch()
        layout.addLayout(row2)

        # フォントサイズ調整ボタン
        font_row = QHBoxLayout()
        font_row.addStretch()
        btn_fd = QPushButton("A-")
        btn_fd.setFixedWidth(36)
        btn_fd.setToolTip("文字を小さくする")
        btn_fd.clicked.connect(lambda: self._adjust_font(-1))
        btn_fu = QPushButton("A+")
        btn_fu.setFixedWidth(36)
        btn_fu.setToolTip("文字を大きくする")
        btn_fu.clicked.connect(lambda: self._adjust_font(1))
        font_row.addWidget(btn_fd)
        font_row.addWidget(btn_fu)
        layout.addLayout(font_row)

        # 一覧テーブル
        self._table = QTableWidget(0, 10)
        self._table.setHorizontalHeaderLabels([
            "写真",
            "会員番号", "会議所役職", "事業所名", "事業所名フリガナ",
            "氏名", "氏名フリガナ", "役職名",
            "メール(件数)", "最終更新日",
        ])
        self._table.horizontalHeader().setSectionResizeMode(
            3, QHeaderView.ResizeMode.Interactive)
        self._table.setColumnWidth(0, 44)
        self._table.setColumnWidth(3, 200)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.doubleClicked.connect(self._edit)
        self._table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._table.customContextMenuRequested.connect(self._show_context_menu)
        self._table.itemSelectionChanged.connect(self._on_selection_changed)

        from app.services.settings_service import get_font_size
        from PyQt6.QtGui import QFont as _QFont
        _sys_pt = self._table.font().pointSize()
        _saved_pt = get_font_size("member_tab", _sys_pt)
        _f = self._table.font()
        _f.setPointSize(_saved_pt)
        self._table.setFont(_f)
        self._table.verticalHeader().setDefaultSectionSize(
            52 + (_saved_pt - _sys_pt) * 2)

        layout.addWidget(self._table)

        self._empty_hint = QLabel(
            "会員データがまだ登録されていません。「追加」ボタン、または"
            "「ファイル→インポート」から会員を登録してください。")
        self._empty_hint.setStyleSheet("color: #64748B; padding: 8px;")
        self._empty_hint.setVisible(False)
        layout.addWidget(self._empty_hint)

        self._count_label = QLabel("")
        layout.addWidget(self._count_label)

    def _adjust_font(self, delta: int):
        from app.services.settings_service import set_font_size
        f = self._table.font()
        new_size = max(6, f.pointSize() + delta)
        f.setPointSize(new_size)
        self._table.setFont(f)
        vh = self._table.verticalHeader()
        vh.setDefaultSectionSize(max(20, vh.defaultSectionSize() + delta * 2))
        set_font_size("member_tab", new_size)

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
        self._table.setSortingEnabled(False)
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
            from app.services.photo_service import bytes_to_pixmap
            from PyQt6.QtCore import Qt as _Qt
            for m in members:
                row = self._table.rowCount()
                self._table.insertRow(row)
                is_retired = not m.is_active
                pos_name = m.position.name if m.position else ""

                # Col 0: 写真
                photo_item = QTableWidgetItem()
                photo_item.setData(Qt.ItemDataRole.UserRole, m.id)
                photo_item.setData(Qt.ItemDataRole.UserRole + 1, m.is_active)
                if m.photo_thumb:
                    pix = bytes_to_pixmap(m.photo_thumb)
                    if pix:
                        pix = pix.scaled(38, 48,
                                         _Qt.AspectRatioMode.KeepAspectRatio,
                                         _Qt.TransformationMode.SmoothTransformation)
                        photo_item.setData(Qt.ItemDataRole.DecorationRole, pix)
                self._table.setItem(row, 0, photo_item)

                # Cols 1-7: テキスト（旧 0-6）
                values = [
                    m.member_number,
                    pos_name,
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

                # Col 8: メール件数（詳細は編集画面で確認）
                item = QTableWidgetItem(f"{len(m.email_addresses)}件")
                if is_retired:
                    item.setForeground(gray)
                self._table.setItem(row, 8, item)

                # Col 9: 最終更新日
                upd = m.updated_at.strftime("%Y/%m/%d") if m.updated_at else ""
                item = QTableWidgetItem(upd)
                if is_retired:
                    item.setForeground(gray)
                self._table.setItem(row, 9, item)
            active_count = sum(1 for m in members if m.is_active)
            if active_only:
                self._count_label.setText(f"{len(members)} 件")
            else:
                retired_count = len(members) - active_count
                self._count_label.setText(
                    f"{active_count} 件（議員退任者 {retired_count} 件を含む）")

            self._update_empty_hint_visibility()
        finally:
            session.close()
        self._table.setSortingEnabled(True)
        self._on_selection_changed()

    def _on_selection_changed(self):
        has_selection = self._table.currentRow() >= 0
        self._btn_edit.setEnabled(has_selection)
        self._btn_history.setEnabled(has_selection)
        self._btn_retire.setEnabled(has_selection)

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

    def _show_context_menu(self, pos: QPoint):
        if self._table.currentRow() < 0:
            return
        menu = QMenu(self)
        menu.addAction("編集", self._edit)
        menu.addAction("変更履歴", self._show_history)
        menu.addSeparator()
        menu.addAction("議員退任", self._delete)
        menu.exec(self._table.viewport().mapToGlobal(pos))

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
            QMessageBox.StandardButton.No,
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

    def _import_revert(self):
        from app.ui.dialogs.import_revert_dialog import ImportRevertDialog
        session = get_session()
        dlg = ImportRevertDialog(session, parent=self)
        if dlg.exec():
            self._load()
        session.close()

    def _export(self):
        from PyQt6.QtWidgets import QFileDialog
        from app.services.export_service import export_members_xlsx, export_members_csv
        path, selected_filter = QFileDialog.getSaveFileName(
            self, "名簿をエクスポート", "名簿.xlsx",
            "Excel (*.xlsx);;CSV (*.csv)"
        )
        if not path:
            return
        session = get_session()
        try:
            if path.lower().endswith(".csv"):
                count = export_members_csv(session, path)
            else:
                count = export_members_xlsx(session, path)
            QMessageBox.information(
                self, "エクスポート完了",
                f"{count}件をエクスポートしました。\n{path}"
            )
        except Exception as e:
            QMessageBox.critical(self, "エラー", str(e))
        finally:
            session.close()
