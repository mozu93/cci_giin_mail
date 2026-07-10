from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QCheckBox, QLabel, QLineEdit, QPushButton,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor
from app.services.settings_service import get_font_size, set_font_size
from app.utils import to_katakana

_NO_EMAIL_TEXT = "（メール無し）"
_ORANGE = QColor("#F97316")


class RecipientPanel(QWidget):
    """送信先テーブル＋検索＋カウント表示をまとめたウィジェット"""

    selection_changed = pyqtSignal(int, int)  # (checked_count, no_email_count)

    def __init__(self):
        super().__init__()
        self._members: list = []
        self._build()

    # ─── 公開API ───────────────────────────────────────────

    def load_members(self, members: list):
        self._members = members
        self._table.setUpdatesEnabled(False)
        self._table.setRowCount(0)
        for m in members:
            self._append_row(m, checked=False)
        self._table.setUpdatesEnabled(True)
        self._update_count()

    def get_selected_members(self) -> list:
        member_cache = {m.id: m for m in self._members}
        seen_ids: set = set()
        result = []
        for row in range(self._table.rowCount()):
            cb = self._table.cellWidget(row, 0)
            if not (cb and cb.isChecked()):
                continue
            item = self._table.item(row, 3)
            mid = item.data(Qt.ItemDataRole.UserRole) if item else None
            if mid and mid not in seen_ids:
                m = member_cache.get(mid)
                if m:
                    result.append(m)
                    seen_ids.add(mid)
        return result

    def set_checks_by_member_ids(self, member_ids: set):
        self._table.setUpdatesEnabled(False)
        for row in range(self._table.rowCount()):
            item = self._table.item(row, 3)
            mid = item.data(Qt.ItemDataRole.UserRole) if item else None
            cb = self._table.cellWidget(row, 0)
            if cb and mid is not None:
                cb.blockSignals(True)
                cb.setChecked(mid in member_ids)
                cb.blockSignals(False)
        self._table.setUpdatesEnabled(True)
        self._update_count()

    def clear_checks(self):
        self._table.setUpdatesEnabled(False)
        for row in range(self._table.rowCount()):
            cb = self._table.cellWidget(row, 0)
            if cb:
                cb.blockSignals(True)
                cb.setChecked(False)
                cb.blockSignals(False)
        self._table.setUpdatesEnabled(True)
        self._update_count()

    def select_all_visible(self):
        self._table.setUpdatesEnabled(False)
        for row in range(self._table.rowCount()):
            if self._table.isRowHidden(row):
                continue
            cb = self._table.cellWidget(row, 0)
            if cb:
                cb.blockSignals(True)
                cb.setChecked(True)
                cb.blockSignals(False)
        self._table.setUpdatesEnabled(True)
        self._update_count()

    def clear_visible(self):
        self._table.setUpdatesEnabled(False)
        for row in range(self._table.rowCount()):
            if self._table.isRowHidden(row):
                continue
            cb = self._table.cellWidget(row, 0)
            if cb:
                cb.blockSignals(True)
                cb.setChecked(False)
                cb.blockSignals(False)
        self._table.setUpdatesEnabled(True)
        self._update_count()

    def filter(self, keyword: str):
        if not keyword:
            for row in range(self._table.rowCount()):
                self._table.setRowHidden(row, False)
            return
        kw = to_katakana(keyword).lower()
        for row in range(self._table.rowCount()):
            match = any(
                (item := self._table.item(row, col)) and kw in item.text().lower()
                for col in (1, 3, 5, 7, 8)
            )
            self._table.setRowHidden(row, not match)

    # ─── UI構築 ────────────────────────────────────────────

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(4)

        hdr = QHBoxLayout()
        hdr.addWidget(QLabel("<b>送信先一覧</b>"))
        hdr.addStretch()
        self._count_label = QLabel("0件選択")
        hdr.addWidget(self._count_label)
        layout.addLayout(hdr)

        search_row = QHBoxLayout()
        self._search = QLineEdit()
        self._search.setPlaceholderText("絞り込み（会員番号・事業所名・氏名）")
        self._search.textChanged.connect(
            lambda text: self.filter(text))
        from app.ui.widgets.search_style import style_search_input
        style_search_input(self._search, max_width=320)
        search_row.addWidget(self._search, 1)
        layout.addLayout(search_row)

        btn_row = QHBoxLayout()
        btn_select_all = QPushButton("全選択")
        btn_select_all.setToolTip("表示中の行を全選択")
        btn_select_all.clicked.connect(self.select_all_visible)
        btn_clear_visible = QPushButton("全解除")
        btn_clear_visible.setToolTip("表示中の行を全解除")
        btn_clear_visible.clicked.connect(self.clear_visible)
        btn_row.addWidget(btn_select_all)
        btn_row.addWidget(btn_clear_visible)
        btn_row.addStretch()
        btn_fd = QPushButton("A-")
        btn_fd.setFixedWidth(36)
        btn_fd.setToolTip("文字を小さくする")
        btn_fd.clicked.connect(lambda: self._adjust_font(-1))
        btn_fu = QPushButton("A+")
        btn_fu.setFixedWidth(36)
        btn_fu.setToolTip("文字を大きくする")
        btn_fu.clicked.connect(lambda: self._adjust_font(1))
        btn_row.addWidget(btn_fd)
        btn_row.addWidget(btn_fu)
        layout.addLayout(btn_row)

        self._table = QTableWidget(0, 9)
        self._table.setHorizontalHeaderLabels(
            ["送信", "会員番号", "会議所役職名", "事業所名", "役職名", "氏名",
             "メールアドレス", "事業所名フリガナ", "氏名フリガナ"])
        h = self._table.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        for col in range(1, 7):
            h.setSectionResizeMode(col, QHeaderView.ResizeMode.Interactive)
        self._table.setColumnWidth(0, 44)
        self._table.setColumnWidth(1, 70)
        self._table.setColumnWidth(2, 110)
        self._table.setColumnWidth(3, 200)
        self._table.setColumnWidth(4, 90)
        self._table.setColumnWidth(5, 90)
        self._table.setColumnWidth(6, 200)
        self._table.setColumnHidden(7, True)
        self._table.setColumnHidden(8, True)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)

        _sys_pt = self._table.font().pointSize()
        _saved_pt = get_font_size("send_tab", _sys_pt)
        _f = self._table.font()
        _f.setPointSize(_saved_pt)
        self._table.setFont(_f)
        self._table.verticalHeader().setDefaultSectionSize(
            self._table.verticalHeader().defaultSectionSize()
            + (_saved_pt - _sys_pt) * 2)

        layout.addWidget(self._table)

        self._no_email_label = QLabel("")
        self._no_email_label.setStyleSheet("color: #DC2626;")
        layout.addWidget(self._no_email_label)

    def _append_row(self, member, checked: bool):
        from app.utils import to_katakana as _kana
        pos_name = member.position.name if member.position else ""
        org_kana = _kana(member.organization_kana or "")
        name_kana = _kana(member.name_kana or "")

        emails = member.email_addresses if member.email_addresses else [None]
        for email in emails:
            row = self._table.rowCount()
            self._table.insertRow(row)
            cb = QCheckBox()
            cb.setChecked(checked)
            cb.stateChanged.connect(self._update_count)
            self._table.setCellWidget(row, 0, cb)
            self._table.setItem(row, 1, QTableWidgetItem(member.member_number))
            self._table.setItem(row, 2, QTableWidgetItem(pos_name))
            org_item = QTableWidgetItem(member.organization_name)
            org_item.setData(Qt.ItemDataRole.UserRole, member.id)
            self._table.setItem(row, 3, org_item)
            self._table.setItem(row, 4, QTableWidgetItem(member.title or ""))
            name_item = QTableWidgetItem(member.name)
            self._table.setItem(row, 5, name_item)
            if email:
                self._table.setItem(row, 6, QTableWidgetItem(email.address))
            else:
                addr_item = QTableWidgetItem(_NO_EMAIL_TEXT)
                addr_item.setForeground(_ORANGE)
                org_item.setForeground(_ORANGE)
                name_item.setForeground(_ORANGE)
                self._table.setItem(row, 6, addr_item)
            self._table.setItem(row, 7, QTableWidgetItem(org_kana))
            self._table.setItem(row, 8, QTableWidgetItem(name_kana))

    def _update_count(self):
        checked = no_email = 0
        for row in range(self._table.rowCount()):
            cb = self._table.cellWidget(row, 0)
            if cb and cb.isChecked():
                checked += 1
                item = self._table.item(row, 6)
                if item and item.text() == _NO_EMAIL_TEXT:
                    no_email += 1
        self._count_label.setText(f"{checked}件選択")
        if no_email:
            self._no_email_label.setText(
                f"⚠ メール無し {no_email}件が含まれています（送信時スキップ）")
        else:
            self._no_email_label.setText("")
        self.selection_changed.emit(checked, no_email)

    def _adjust_font(self, delta: int):
        f = self._table.font()
        new_size = max(6, f.pointSize() + delta)
        f.setPointSize(new_size)
        self._table.setFont(f)
        vh = self._table.verticalHeader()
        vh.setDefaultSectionSize(max(20, vh.defaultSectionSize() + delta * 2))
        set_font_size("send_tab", new_size)

    @property
    def table(self) -> QTableWidget:
        """build_targets が列参照で使う内部テーブルへの直接アクセス"""
        return self._table

    @property
    def no_email_text(self) -> str:
        return _NO_EMAIL_TEXT
