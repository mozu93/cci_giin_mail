from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QCheckBox, QLabel, QLineEdit, QPushButton,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor
from app.services.settings_service import get_font_size, set_font_size
from app.services.member_service import committee_role_display
from app.utils import to_katakana

_NO_EMAIL_TEXT = "（メール無し）"
_ORANGE = QColor("#F97316")

# 2列目「委員会役職」は委員会で絞り込んでいる時だけ表示する
_COL_CHECK = 0
_COL_MEMBER_NO = 1
_COL_COMMITTEE_ROLE = 2
_COL_POSITION = 3
_COL_ORG = 4
_COL_TITLE = 5
_COL_NAME = 6
_COL_EMAIL = 7
_COL_ORG_KANA = 8
_COL_NAME_KANA = 9


class RecipientPanel(QWidget):
    """送信先テーブル＋検索＋カウント表示をまとめたウィジェット"""

    selection_changed = pyqtSignal(int, int)  # (checked_count, no_email_count)

    def __init__(self):
        super().__init__()
        self._members: list = []
        self._keyword: str = ""
        self._id_restriction: set | None = None
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
            item = self._table.item(row, _COL_ORG)
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
            item = self._table.item(row, _COL_ORG)
            mid = item.data(Qt.ItemDataRole.UserRole) if item else None
            cb = self._table.cellWidget(row, 0)
            if cb and mid is not None:
                cb.blockSignals(True)
                cb.setChecked(mid in member_ids)
                cb.blockSignals(False)
        self._table.setUpdatesEnabled(True)
        self._update_count()

    def set_committee_role_column_visible(self, visible: bool):
        """委員会で絞り込んでいる時だけ「委員会役職」列を表示する"""
        self._table.setColumnHidden(_COL_COMMITTEE_ROLE, not visible)

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
        self._keyword = keyword or ""
        self._apply_row_visibility()

    def restrict_to_member_ids(self, member_ids: set | None):
        """委員会・役職などの絞り込みモードで一致した会員だけを一覧に残す。
        None を渡すと絞り込みを解除する（名簿から選択モードなど）。"""
        self._id_restriction = member_ids
        self._apply_row_visibility()

    def _apply_row_visibility(self):
        kw = to_katakana(self._keyword).lower() if self._keyword else ""
        for row in range(self._table.rowCount()):
            if self._id_restriction is not None:
                org_item = self._table.item(row, _COL_ORG)
                mid = org_item.data(Qt.ItemDataRole.UserRole) if org_item else None
                if mid not in self._id_restriction:
                    self._table.setRowHidden(row, True)
                    continue
            if not kw:
                self._table.setRowHidden(row, False)
                continue
            match = any(
                (item := self._table.item(row, col)) and kw in item.text().lower()
                for col in (_COL_MEMBER_NO, _COL_ORG, _COL_NAME, _COL_ORG_KANA, _COL_NAME_KANA)
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
        self._count_label = QLabel("0社選択")
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

        self._table = QTableWidget(0, 10)
        self._table.setHorizontalHeaderLabels(
            ["送信", "会員番号", "委員会役職", "会議所役職名", "事業所名", "役職名", "氏名",
             "メールアドレス（To／CC）", "事業所名フリガナ", "氏名フリガナ"])
        h = self._table.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        for col in range(1, 8):
            h.setSectionResizeMode(col, QHeaderView.ResizeMode.Interactive)
        self._table.setColumnWidth(0, 44)
        self._table.setColumnWidth(_COL_MEMBER_NO, 70)
        self._table.setColumnWidth(_COL_COMMITTEE_ROLE, 90)
        self._table.setColumnWidth(_COL_POSITION, 110)
        self._table.setColumnWidth(_COL_ORG, 200)
        self._table.setColumnWidth(_COL_TITLE, 90)
        self._table.setColumnWidth(_COL_NAME, 90)
        self._table.setColumnWidth(_COL_EMAIL, 360)
        self._table.setColumnHidden(_COL_COMMITTEE_ROLE, True)
        self._table.setColumnHidden(_COL_ORG_KANA, True)
        self._table.setColumnHidden(_COL_NAME_KANA, True)
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

        row = self._table.rowCount()
        self._table.insertRow(row)
        cb = QCheckBox()
        cb.setChecked(checked)
        cb.stateChanged.connect(self._update_count)
        self._table.setCellWidget(row, 0, cb)
        self._table.setItem(row, _COL_MEMBER_NO, QTableWidgetItem(member.member_number))
        self._table.setItem(
            row, _COL_COMMITTEE_ROLE, QTableWidgetItem(committee_role_display(member)))
        self._table.setItem(row, _COL_POSITION, QTableWidgetItem(pos_name))
        org_item = QTableWidgetItem(member.organization_name)
        org_item.setData(Qt.ItemDataRole.UserRole, member.id)
        self._table.setItem(row, _COL_ORG, org_item)
        self._table.setItem(row, _COL_TITLE, QTableWidgetItem(member.title or ""))
        name_item = QTableWidgetItem(member.name)
        self._table.setItem(row, _COL_NAME, name_item)
        if member.email_addresses:
            addresses = [email.address for email in member.email_addresses]
            address_text = f"To: {addresses[0]}"
            if len(addresses) > 1:
                address_text += f" / CC: {', '.join(addresses[1:])}"
            self._table.setItem(row, _COL_EMAIL, QTableWidgetItem(address_text))
        else:
            addr_item = QTableWidgetItem(_NO_EMAIL_TEXT)
            addr_item.setForeground(_ORANGE)
            org_item.setForeground(_ORANGE)
            name_item.setForeground(_ORANGE)
            self._table.setItem(row, _COL_EMAIL, addr_item)
        self._table.setItem(row, _COL_ORG_KANA, QTableWidgetItem(org_kana))
        self._table.setItem(row, _COL_NAME_KANA, QTableWidgetItem(name_kana))

    def _update_count(self):
        checked = no_email = 0
        checked_member_ids: set = set()
        for row in range(self._table.rowCount()):
            cb = self._table.cellWidget(row, 0)
            if cb and cb.isChecked():
                checked += 1
                org_item = self._table.item(row, _COL_ORG)
                mid = org_item.data(Qt.ItemDataRole.UserRole) if org_item else None
                if mid is not None:
                    checked_member_ids.add(mid)
                item = self._table.item(row, _COL_EMAIL)
                if item and item.text() == _NO_EMAIL_TEXT:
                    no_email += 1
        self._count_label.setText(f"{len(checked_member_ids)}社選択")
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
