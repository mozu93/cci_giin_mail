from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QPushButton, QLabel, QLineEdit, QComboBox, QCheckBox,
    QFileDialog, QMessageBox, QApplication,
)
from PyQt6.QtCore import Qt
from app.database.connection import get_session
from app.services.meeting_service import STATUS_OPTIONS, upsert_attendance, get_attendance_data, export_csv
from app.services.settings_service import get_font_size, set_font_size
from app.utils import to_katakana
from app.ui.meeting_widgets import count_label

_PRE_COL_KEYS = ["position", "org_name", "org_kana", "title", "name",
                 "status", "proxy_title", "proxy_name"]
_PRE_HEADERS  = ["会議所役職名", "事業所名", "事業所名フリガナ", "役職名", "氏名",
                 "ステータス", "代理役職名", "代理者氏名"]


class PreentryWidget(QWidget):
    def __init__(self, readonly: bool = False):
        super().__init__()
        self._readonly = readonly
        self._meeting_id: int | None = None
        self._preentry_data: list[dict] = []
        self._sort_keys: list[tuple[int, bool]] = []
        self._original_ids: list[int] = []
        self._build()

    def load(self, meeting_id: int | None):
        self._meeting_id = meeting_id
        self._load_preentry()

    # ─── UI構築 ────────────────────────────────────────────

    def _build(self):
        layout = QVBoxLayout(self)

        pre_grp = QGroupBox("出欠集計")
        pre_cnt = QHBoxLayout(pre_grp)
        self._lbl_attend     = count_label("出席: 0",  "#16A34A")
        self._lbl_proxy      = count_label("代理: 0",  "#2563EB")
        self._lbl_delegate   = count_label("委任: 0",  "#CA8A04")
        self._lbl_absent     = count_label("欠席: 0",  "#DC2626")
        self._lbl_unanswered = count_label("未回答: 0", "#6B7280")
        self._lbl_total      = count_label("合計: 0",  "#1E40AF", bold=True)
        for lbl in [self._lbl_attend, self._lbl_proxy, self._lbl_delegate,
                    self._lbl_absent, self._lbl_unanswered, self._lbl_total]:
            pre_cnt.addWidget(lbl)
        pre_cnt.addStretch()
        layout.addWidget(pre_grp)

        btn_row = QHBoxLayout()
        if not self._readonly:
            btn_reset = QPushButton("並び替え解除")
            btn_reset.clicked.connect(self._reset_sort)
            btn_row.addWidget(btn_reset)
        self._pre_search = QLineEdit()
        self._pre_search.setPlaceholderText("事業所名・事業所名フリガナで検索")
        self._pre_search.textChanged.connect(self._apply_status_filter)
        from app.ui.widgets.search_style import style_search_input
        style_search_input(self._pre_search)
        btn_csv = QPushButton("CSV出力")
        btn_csv.clicked.connect(self._export_csv)
        btn_fd = QPushButton("A-")
        btn_fd.setFixedWidth(36)
        btn_fd.setToolTip("文字を小さくする")
        btn_fd.clicked.connect(lambda: self._adjust_font(-1))
        btn_fu = QPushButton("A+")
        btn_fu.setFixedWidth(36)
        btn_fu.setToolTip("文字を大きくする")
        btn_fu.clicked.connect(lambda: self._adjust_font(1))
        btn_row.addWidget(self._pre_search, 2)
        btn_row.addStretch()
        btn_row.addWidget(btn_csv)
        btn_row.addWidget(btn_fd)
        btn_row.addWidget(btn_fu)
        layout.addLayout(btn_row)

        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("表示:"))
        self._status_filter_checks: dict[str, QCheckBox] = {}
        for s in STATUS_OPTIONS:
            cb = QCheckBox(s)
            cb.setChecked(True)
            cb.stateChanged.connect(self._apply_status_filter)
            filter_row.addWidget(cb)
            self._status_filter_checks[s] = cb
        btn_all_on = QPushButton("全選択")
        btn_all_on.clicked.connect(self._select_all_status_filter)
        btn_all_off = QPushButton("全解除")
        btn_all_off.clicked.connect(self._clear_status_filter)
        filter_row.addWidget(btn_all_on)
        filter_row.addWidget(btn_all_off)
        filter_row.addStretch()
        layout.addLayout(filter_row)

        self._pre_table = QTableWidget(0, len(_PRE_HEADERS))
        self._pre_table.setHorizontalHeaderLabels(_PRE_HEADERS)
        h = self._pre_table.horizontalHeader()
        h.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self._pre_table.setColumnWidth(0, 120)
        self._pre_table.setColumnWidth(1, 200)
        self._pre_table.setColumnWidth(2, 150)
        self._pre_table.setColumnWidth(3, 100)
        self._pre_table.setColumnWidth(4, 100)
        self._pre_table.setColumnWidth(5, 80)
        self._pre_table.setColumnWidth(6, 110)
        self._pre_table.setColumnWidth(7, 110)
        h.sectionClicked.connect(self._on_pre_header_click)
        self._pre_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._pre_table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        _sys_pt = self._pre_table.font().pointSize()
        _saved_pt = get_font_size("preentry_tab", _sys_pt)
        _f = self._pre_table.font()
        _f.setPointSize(_saved_pt)
        self._pre_table.setFont(_f)
        self._pre_table.verticalHeader().setDefaultSectionSize(
            self._pre_table.verticalHeader().defaultSectionSize()
            + (_saved_pt - _sys_pt) * 2)
        layout.addWidget(self._pre_table)

    # ─── データ操作 ────────────────────────────────────────

    def _adjust_font(self, delta: int):
        f = self._pre_table.font()
        new_size = max(6, f.pointSize() + delta)
        f.setPointSize(new_size)
        self._pre_table.setFont(f)
        vh = self._pre_table.verticalHeader()
        vh.setDefaultSectionSize(max(20, vh.defaultSectionSize() + delta * 2))
        set_font_size("preentry_tab", new_size)

    def _load_preentry(self):
        self._pre_table.setRowCount(0)
        if not self._meeting_id:
            return
        session = get_session()
        try:
            self._preentry_data = get_attendance_data(session, self._meeting_id)
        finally:
            session.close()
        self._sort_keys.clear()
        self._original_ids = [d["member_id"] for d in self._preentry_data]
        self._update_pre_headers()
        self._render_preentry()

    def _render_preentry(self):
        self._pre_table.setUpdatesEnabled(False)
        self._pre_table.setRowCount(0)
        for i, d in enumerate(self._preentry_data):
            self._pre_table.insertRow(i)
            for col in range(5):
                self._pre_table.setItem(
                    i, col, QTableWidgetItem(d.get(_PRE_COL_KEYS[col], "")))
            if self._readonly:
                self._pre_table.setItem(i, 5, QTableWidgetItem(d["status"]))
                self._pre_table.setItem(
                    i, 6, QTableWidgetItem(d.get("proxy_title", "")))
                self._pre_table.setItem(
                    i, 7, QTableWidgetItem(d.get("proxy_name", "")))
            else:
                mid = d["member_id"]
                combo = QComboBox()
                combo.addItems(STATUS_OPTIONS)
                combo.setCurrentText(d["status"])
                combo.currentTextChanged.connect(
                    lambda text, m=mid: self._on_status_change_by_id(m, text))
                self._pre_table.setCellWidget(i, 5, combo)
                is_proxy = d["status"] == "代理"
                title_edit = QLineEdit(d["proxy_title"])
                name_edit  = QLineEdit(d["proxy_name"])
                title_edit.setEnabled(is_proxy)
                name_edit.setEnabled(is_proxy)
                title_edit.editingFinished.connect(
                    lambda m=mid: self._save_proxy_by_id(m))
                name_edit.editingFinished.connect(
                    lambda m=mid: self._save_proxy_by_id(m))
                self._pre_table.setCellWidget(i, 6, title_edit)
                self._pre_table.setCellWidget(i, 7, name_edit)
        self._pre_table.setUpdatesEnabled(True)
        self._apply_status_filter()
        self._update_preentry_summary()

    def _apply_status_filter(self):
        visible = {s for s, cb in self._status_filter_checks.items() if cb.isChecked()}
        keyword = to_katakana(self._pre_search.text().strip())
        for row in range(self._pre_table.rowCount()):
            if row >= len(self._preentry_data):
                continue
            d = self._preentry_data[row]
            status_ok = d["status"] in visible
            search_ok = (not keyword
                         or keyword in to_katakana(d.get("org_name", ""))
                         or keyword in to_katakana(d.get("org_kana", "")))
            self._pre_table.setRowHidden(row, not (status_ok and search_ok))

    def _select_all_status_filter(self):
        for cb in self._status_filter_checks.values():
            cb.blockSignals(True)
            cb.setChecked(True)
            cb.blockSignals(False)
        self._apply_status_filter()

    def _clear_status_filter(self):
        for cb in self._status_filter_checks.values():
            cb.blockSignals(True)
            cb.setChecked(False)
            cb.blockSignals(False)
        self._apply_status_filter()

    def _update_preentry_summary(self):
        counts: dict[str, int] = {"出席": 0, "代理": 0, "委任": 0, "欠席": 0, "未回答": 0}
        for d in self._preentry_data:
            s = d["status"]
            if s in counts:
                counts[s] += 1
        total = counts["出席"] + counts["代理"] + counts["委任"]
        self._lbl_attend.setText(f"出席: {counts['出席']}")
        self._lbl_proxy.setText(f"代理: {counts['代理']}")
        self._lbl_delegate.setText(f"委任: {counts['委任']}")
        self._lbl_absent.setText(f"欠席: {counts['欠席']}")
        self._lbl_unanswered.setText(f"未回答: {counts['未回答']}")
        self._lbl_total.setText(f"合計: {total}")

    def _on_pre_header_click(self, col: int):
        shift = bool(
            QApplication.keyboardModifiers() & Qt.KeyboardModifier.ShiftModifier)
        existing = next(
            (i for i, (c, _) in enumerate(self._sort_keys) if c == col), None)
        if shift:
            if existing is not None:
                old_asc = self._sort_keys[existing][1]
                self._sort_keys[existing] = (col, not old_asc)
            else:
                self._sort_keys.append((col, True))
        else:
            if existing == 0 and len(self._sort_keys) == 1:
                self._sort_keys = [(col, not self._sort_keys[0][1])]
            else:
                self._sort_keys = [(col, True)]
        self._apply_sort()
        self._update_pre_headers()
        self._render_preentry()

    def _apply_sort(self):
        for col, ascending in reversed(self._sort_keys):
            key = _PRE_COL_KEYS[col]
            self._preentry_data.sort(
                key=lambda d, k=key: d.get(k, ""),
                reverse=not ascending,
            )

    def _update_pre_headers(self):
        rank_sym = "①②③④⑤⑥⑦⑧"
        labels = []
        for col, base in enumerate(_PRE_HEADERS):
            for rank, (c, asc) in enumerate(self._sort_keys):
                if c == col:
                    arrow = "↑" if asc else "↓"
                    sym = rank_sym[rank] if rank < len(rank_sym) else str(rank + 1)
                    labels.append(f"{base} {arrow}{sym}")
                    break
            else:
                labels.append(base)
        self._pre_table.setHorizontalHeaderLabels(labels)

    def _reset_sort(self):
        self._sort_keys.clear()
        if self._original_ids:
            id_to_d = {d["member_id"]: d for d in self._preentry_data}
            self._preentry_data = [
                id_to_d[mid] for mid in self._original_ids if mid in id_to_d]
        self._update_pre_headers()
        self._render_preentry()

    def _find_row(self, member_id: int) -> int:
        return next(
            (i for i, d in enumerate(self._preentry_data) if d["member_id"] == member_id),
            -1,
        )

    def _on_status_change_by_id(self, member_id: int, text: str):
        row = self._find_row(member_id)
        if row >= 0:
            self._on_status_change(row, text)

    def _save_proxy_by_id(self, member_id: int):
        row = self._find_row(member_id)
        if row >= 0:
            self._save_proxy(row)

    def _on_status_change(self, row: int, text: str):
        if row >= len(self._preentry_data):
            return
        d = self._preentry_data[row]
        d["status"] = text
        title_edit = self._pre_table.cellWidget(row, 6)
        name_edit  = self._pre_table.cellWidget(row, 7)
        is_proxy = (text == "代理")
        if title_edit:
            title_edit.setEnabled(is_proxy)
        if name_edit:
            name_edit.setEnabled(is_proxy)
        if not is_proxy:
            d["proxy_title"] = ""
            d["proxy_name"] = ""
            if title_edit:
                title_edit.setText("")
            if name_edit:
                name_edit.setText("")
        self._save_row(row)
        self._apply_status_filter()
        self._update_preentry_summary()

    def _save_proxy(self, row: int):
        if row >= len(self._preentry_data):
            return
        d = self._preentry_data[row]
        title_edit = self._pre_table.cellWidget(row, 6)
        name_edit  = self._pre_table.cellWidget(row, 7)
        d["proxy_title"] = title_edit.text().strip() if title_edit else ""
        d["proxy_name"]  = name_edit.text().strip() if name_edit else ""
        self._save_row(row)

    def _save_row(self, row: int):
        if row >= len(self._preentry_data) or not self._meeting_id:
            return
        d = self._preentry_data[row]
        session = get_session()
        try:
            upsert_attendance(
                session, self._meeting_id, d["member_id"],
                d["status"], d["proxy_title"], d["proxy_name"])
        finally:
            session.close()

    def _export_csv(self):
        if not self._meeting_id:
            QMessageBox.warning(self, "エラー", "会議を選択してください。")
            return
        path, _ = QFileDialog.getSaveFileName(self, "CSV保存", "", "CSV (*.csv)")
        if not path:
            return
        session = get_session()
        try:
            export_csv(session, self._meeting_id, path)
        finally:
            session.close()
        QMessageBox.information(self, "完了", f"CSVを保存しました。\n{path}")
