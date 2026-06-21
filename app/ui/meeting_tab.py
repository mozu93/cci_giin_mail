# app/ui/meeting_tab.py
import unicodedata
from datetime import date
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QPushButton, QLabel, QLineEdit, QComboBox,
    QDialog, QFormLayout, QDateEdit, QMessageBox,
    QFileDialog, QTabWidget, QRadioButton, QButtonGroup, QCheckBox,
    QApplication
)
from PyQt6.QtCore import Qt, QTimer, QDate
from PyQt6.QtGui import QColor
from app.database.connection import get_session
from app.services.meeting_service import (
    STATUS_OPTIONS, create_meeting, get_meetings, delete_meeting,
    upsert_attendance, get_attendance_data, get_summary, export_csv,
    update_actual_status, get_reception_summary
)
from app.services.position_service import get_positions

def _to_katakana(text: str) -> str:
    """ひらがな・半角カタカナを全角カタカナに統一して返す"""
    text = unicodedata.normalize("NFKC", text)   # 半角カタカナ → 全角カタカナ
    return "".join(
        chr(ord(ch) + 0x60) if 0x3041 <= ord(ch) <= 0x3096 else ch
        for ch in text
    )


_PRE_COL_KEYS = ["position", "org_name", "org_kana", "title", "name",
                 "status", "proxy_title", "proxy_name"]
_PRE_HEADERS  = ["会議所役職名", "事業所名", "事業所名フリガナ", "役職名", "氏名",
                 "ステータス", "代理役職名", "代理者氏名"]

_STATUS_COLORS = {
    "出席": "#DCFCE7",
    "代理": "#DBEAFE",
    "委任": "#FEF9C3",
    "欠席": "#FEE2E2",
}


class _NewMeetingDialog(QDialog):
    def __init__(self, positions: list, parent=None):
        super().__init__(parent)
        self.setWindowTitle("会議作成")
        self.setMinimumWidth(340)
        layout = QVBoxLayout(self)

        form = QFormLayout()
        self._name = QLineEdit()
        self._name.setPlaceholderText("例: 第50回定時総会")
        self._date = QDateEdit(QDate.currentDate())
        self._date.setCalendarPopup(True)
        self._date.setDisplayFormat("yyyy/MM/dd")
        form.addRow("会議名", self._name)
        form.addRow("開催日", self._date)
        layout.addLayout(form)

        # 対象者選択
        target_grp = QGroupBox("対象者")
        target_layout = QVBoxLayout(target_grp)
        self._rb_all = QRadioButton("全員（総会など）")
        self._rb_pos = QRadioButton("役職指定（常議員会など）")
        self._rb_all.setChecked(True)
        btn_grp = QButtonGroup(self)
        btn_grp.addButton(self._rb_all)
        btn_grp.addButton(self._rb_pos)
        target_layout.addWidget(self._rb_all)
        target_layout.addWidget(self._rb_pos)

        self._pos_widget = QWidget()
        pos_layout = QVBoxLayout(self._pos_widget)
        pos_layout.setContentsMargins(20, 0, 0, 0)
        self._pos_checks: dict[int, QCheckBox] = {}
        for p in positions:
            cb = QCheckBox(p.name)
            pos_layout.addWidget(cb)
            self._pos_checks[p.id] = cb
        self._pos_widget.setVisible(False)
        target_layout.addWidget(self._pos_widget)
        layout.addWidget(target_grp)

        self._rb_pos.toggled.connect(self._pos_widget.setVisible)

        btn_row = QHBoxLayout()
        btn_cancel = QPushButton("キャンセル")
        btn_cancel.clicked.connect(self.reject)
        btn_ok = QPushButton("作成")
        btn_ok.clicked.connect(self._ok)
        btn_ok.setDefault(True)
        btn_row.addWidget(btn_cancel)
        btn_row.addWidget(btn_ok)
        layout.addLayout(btn_row)

    def _ok(self):
        if not self._name.text().strip():
            QMessageBox.warning(self, "エラー", "会議名を入力してください。")
            return
        if self._rb_pos.isChecked() and not any(
                cb.isChecked() for cb in self._pos_checks.values()):
            QMessageBox.warning(self, "エラー", "役職を1つ以上選択してください。")
            return
        self.accept()

    def get_values(self) -> tuple[str, date, list[int] | None]:
        d = self._date.date()
        target_ids = None
        if self._rb_pos.isChecked():
            target_ids = [pid for pid, cb in self._pos_checks.items()
                          if cb.isChecked()]
        return self._name.text().strip(), date(d.year(), d.month(), d.day()), target_ids


class MeetingTab(QWidget):
    def __init__(self):
        super().__init__()
        self._current_meeting_id: int | None = None
        self._preentry_data: list[dict] = []
        self._rec_data: list[dict] = []
        self._sort_keys: list[tuple[int, bool]] = []   # (col_idx, ascending)
        self._original_ids: list[int] = []             # default order
        self._build()
        self._load_meetings()

    # ─── 構築 ──────────────────────────────────────────────────

    def _build(self):
        layout = QVBoxLayout(self)

        # 会議選択ヘッダー
        hdr = QHBoxLayout()
        hdr.addWidget(QLabel("会議:"))
        self._meeting_combo = QComboBox()
        self._meeting_combo.currentIndexChanged.connect(self._on_meeting_select)
        hdr.addWidget(self._meeting_combo, 1)
        btn_new = QPushButton("新規作成")
        btn_new.clicked.connect(self._create_meeting)
        btn_del = QPushButton("削除")
        btn_del.clicked.connect(self._delete_meeting)
        hdr.addWidget(btn_new)
        hdr.addWidget(btn_del)
        layout.addLayout(hdr)

        self._inner = QTabWidget()
        self._inner.addTab(self._build_preentry_tab(), "事前入力")
        self._inner.addTab(self._build_reception_tab(), "受付")
        self._inner.currentChanged.connect(self._on_inner_tab_change)
        layout.addWidget(self._inner)

        self._timer = QTimer()
        self._timer.setInterval(3000)
        self._timer.timeout.connect(self._refresh_reception)

    # ─── 事前入力タブ ──────────────────────────────────────────

    def _build_preentry_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        # 事前入力集計バー（最上部）
        pre_grp = QGroupBox("出欠集計")
        pre_cnt = QHBoxLayout(pre_grp)
        self._pre_lbl_attend     = self._count_label("出席: 0",  "#16A34A")
        self._pre_lbl_proxy      = self._count_label("代理: 0",  "#2563EB")
        self._pre_lbl_delegate   = self._count_label("委任: 0",  "#CA8A04")
        self._pre_lbl_absent     = self._count_label("欠席: 0",  "#DC2626")
        self._pre_lbl_unanswered = self._count_label("未回答: 0", "#6B7280")
        self._pre_lbl_total      = self._count_label("合計: 0",  "#1E40AF", bold=True)
        for lbl in [self._pre_lbl_attend, self._pre_lbl_proxy, self._pre_lbl_delegate,
                    self._pre_lbl_absent, self._pre_lbl_unanswered, self._pre_lbl_total]:
            pre_cnt.addWidget(lbl)
        pre_cnt.addStretch()
        layout.addWidget(pre_grp)

        btn_row = QHBoxLayout()
        btn_reset = QPushButton("並び替え解除")
        btn_reset.clicked.connect(self._reset_sort)
        self._pre_search = QLineEdit()
        self._pre_search.setPlaceholderText("事業所名・事業所名フリガナで検索")
        self._pre_search.textChanged.connect(self._apply_status_filter)
        btn_csv = QPushButton("CSV出力")
        btn_csv.clicked.connect(self._export_csv)
        btn_row.addWidget(btn_reset)
        btn_row.addWidget(self._pre_search, 2)
        btn_row.addStretch()
        btn_row.addWidget(btn_csv)
        layout.addLayout(btn_row)

        # ステータス抽出チェックボックス
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
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        h.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        h.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(6, QHeaderView.ResizeMode.Interactive)
        h.setSectionResizeMode(7, QHeaderView.ResizeMode.Interactive)
        self._pre_table.setColumnWidth(1, 200)
        self._pre_table.setColumnWidth(2, 150)
        self._pre_table.setColumnWidth(6, 110)
        self._pre_table.setColumnWidth(7, 110)
        h.sectionClicked.connect(self._on_pre_header_click)
        self._pre_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._pre_table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        layout.addWidget(self._pre_table)
        return w

    def _load_preentry(self):
        self._pre_table.setRowCount(0)
        if not self._current_meeting_id:
            return
        session = get_session()
        try:
            self._preentry_data = get_attendance_data(
                session, self._current_meeting_id)
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
            for col in range(5):   # 会議所役職名〜氏名（読み取り専用）
                self._pre_table.setItem(
                    i, col, QTableWidgetItem(d.get(_PRE_COL_KEYS[col], "")))
            combo = QComboBox()
            combo.addItems(STATUS_OPTIONS)
            combo.setCurrentText(d["status"])
            combo.currentTextChanged.connect(
                lambda text, row=i: self._on_status_change(row, text))
            self._pre_table.setCellWidget(i, 5, combo)
            is_proxy = d["status"] == "代理"
            title_edit = QLineEdit(d["proxy_title"])
            name_edit  = QLineEdit(d["proxy_name"])
            title_edit.setEnabled(is_proxy)
            name_edit.setEnabled(is_proxy)
            title_edit.editingFinished.connect(lambda row=i: self._save_proxy(row))
            name_edit.editingFinished.connect(lambda row=i: self._save_proxy(row))
            self._pre_table.setCellWidget(i, 6, title_edit)
            self._pre_table.setCellWidget(i, 7, name_edit)
        self._pre_table.setUpdatesEnabled(True)
        self._apply_status_filter()
        self._update_preentry_summary()

    def _apply_status_filter(self):
        visible = {s for s, cb in self._status_filter_checks.items() if cb.isChecked()}
        keyword = _to_katakana(self._pre_search.text().strip())
        for row in range(self._pre_table.rowCount()):
            if row >= len(self._preentry_data):
                continue
            d = self._preentry_data[row]
            status_ok = d["status"] in visible
            search_ok = (not keyword
                         or keyword in _to_katakana(d.get("org_name", ""))
                         or keyword in _to_katakana(d.get("org_kana", "")))
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
        self._pre_lbl_attend.setText(f"出席: {counts['出席']}")
        self._pre_lbl_proxy.setText(f"代理: {counts['代理']}")
        self._pre_lbl_delegate.setText(f"委任: {counts['委任']}")
        self._pre_lbl_absent.setText(f"欠席: {counts['欠席']}")
        self._pre_lbl_unanswered.setText(f"未回答: {counts['未回答']}")
        self._pre_lbl_total.setText(f"合計: {total}")

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
        if row >= len(self._preentry_data) or not self._current_meeting_id:
            return
        d = self._preentry_data[row]
        session = get_session()
        try:
            upsert_attendance(
                session, self._current_meeting_id, d["member_id"],
                d["status"], d["proxy_title"], d["proxy_name"])
        finally:
            session.close()

    def _export_csv(self):
        if not self._current_meeting_id:
            QMessageBox.warning(self, "エラー", "会議を選択してください。")
            return
        path, _ = QFileDialog.getSaveFileName(self, "CSV保存", "", "CSV (*.csv)")
        if not path:
            return
        session = get_session()
        try:
            export_csv(session, self._current_meeting_id, path)
        finally:
            session.close()
        QMessageBox.information(self, "完了", f"CSVを保存しました。\n{path}")

    # ─── 受付タブ ──────────────────────────────────────────────

    def _build_reception_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        # 集計バー（当日受付ベース）
        count_grp = QGroupBox("当日受付集計（3秒ごと自動更新）")
        count_layout = QHBoxLayout(count_grp)
        self._lbl_attend  = self._count_label("出席: 0",   "#16A34A")
        self._lbl_proxy   = self._count_label("代理: 0",   "#2563EB")
        self._lbl_absent  = self._count_label("欠席: 0",   "#DC2626")
        self._lbl_pending = self._count_label("未受付: 0", "#6B7280")
        self._lbl_total   = self._count_label("合計: 0",   "#1E40AF", bold=True)
        for lbl in [self._lbl_attend, self._lbl_proxy,
                    self._lbl_absent, self._lbl_pending, self._lbl_total]:
            count_layout.addWidget(lbl)
        count_layout.addStretch()
        layout.addWidget(count_grp)

        # 検索
        search_row = QHBoxLayout()
        search_row.addWidget(QLabel("検索:"))
        self._search = QLineEdit()
        self._search.setPlaceholderText("事業所名・氏名・会員番号")
        self._search.textChanged.connect(self._filter_reception)
        search_row.addWidget(self._search, 1)
        layout.addLayout(search_row)

        # 一覧（7列）: 会員番号, 事業所名, 会議所役職, 氏名, 事前, 当日受付, 代理情報
        self._rec_table = QTableWidget(0, 7)
        self._rec_table.setHorizontalHeaderLabels(
            ["会員番号", "事業所名", "会議所役職", "氏名", "事前", "当日受付", "代理情報"])
        h = self._rec_table.horizontalHeader()
        h.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        h.setSectionResizeMode(6, QHeaderView.ResizeMode.Interactive)
        self._rec_table.setColumnWidth(1, 200)
        self._rec_table.setColumnWidth(6, 150)
        self._rec_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._rec_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        layout.addWidget(self._rec_table)
        return w

    def _count_label(self, text: str, color: str, bold: bool = False) -> QLabel:
        lbl = QLabel(text)
        weight = "bold" if bold else "normal"
        lbl.setStyleSheet(
            f"font-size: 15px; font-weight: {weight}; color: {color}; padding: 4px 14px;")
        return lbl

    _ACTUAL_OPTIONS = ["", "出席", "代理", "欠席"]

    def _refresh_reception(self):
        if not self._current_meeting_id:
            return
        session = get_session()
        try:
            self._rec_data = get_attendance_data(
                session, self._current_meeting_id)
            summary = get_reception_summary(session, self._current_meeting_id)
        finally:
            session.close()

        self._lbl_attend.setText(f"出席: {summary['出席']}")
        self._lbl_proxy.setText(f"代理: {summary['代理']}")
        self._lbl_absent.setText(f"欠席: {summary['欠席']}")
        self._lbl_pending.setText(f"未受付: {summary['未受付']}")
        self._lbl_total.setText(f"合計: {summary['合計']}")

        scrollbar = self._rec_table.verticalScrollBar()
        scroll_pos = scrollbar.value()
        self._rec_table.setUpdatesEnabled(False)
        self._rec_table.setRowCount(0)
        for d in self._rec_data:
            row = self._rec_table.rowCount()
            self._rec_table.insertRow(row)
            proxy_info = ""
            if d["status"] in ("代理",) or d.get("actual_status") == "代理":
                proxy_info = " ".join(
                    p for p in [d["proxy_title"], d["proxy_name"]] if p)
            # 行の背景色: actual_status が設定済みならその色、未受付なら事前ステータスの色
            effective = d.get("actual_status") or d["status"]
            bg = _STATUS_COLORS.get(effective)
            # 列 0-4: テキストアイテム
            for col, val in enumerate([d["member_number"], d["org_name"],
                                       d["position"], d["name"], d["status"]]):
                item = QTableWidgetItem(val)
                if bg:
                    item.setBackground(QColor(bg))
                self._rec_table.setItem(row, col, item)
            # 列 5: 当日受付 QComboBox
            combo = QComboBox()
            combo.addItems(self._ACTUAL_OPTIONS)
            combo.blockSignals(True)
            combo.setCurrentText(d.get("actual_status") or "")
            combo.blockSignals(False)
            mid = d["member_id"]
            combo.currentTextChanged.connect(
                lambda text, m=mid: self._save_actual_status(m, text))
            self._rec_table.setCellWidget(row, 5, combo)
            # 列 6: 代理情報
            item6 = QTableWidgetItem(proxy_info)
            if bg:
                item6.setBackground(QColor(bg))
            self._rec_table.setItem(row, 6, item6)
        self._rec_table.setUpdatesEnabled(True)
        scrollbar.setValue(scroll_pos)
        self._filter_reception()

    def _save_actual_status(self, member_id: int, actual_status: str):
        if not self._current_meeting_id:
            return
        session = get_session()
        try:
            update_actual_status(
                session, self._current_meeting_id, member_id, actual_status)
        finally:
            session.close()

    def _filter_reception(self):
        keyword = self._search.text().strip().lower()
        for row in range(self._rec_table.rowCount()):
            if not keyword:
                self._rec_table.setRowHidden(row, False)
                continue
            visible = any(
                keyword in (self._rec_table.item(row, col).text()
                            if self._rec_table.item(row, col) else "").lower()
                for col in range(self._rec_table.columnCount())
            )
            self._rec_table.setRowHidden(row, not visible)

    # ─── 会議管理 ──────────────────────────────────────────────

    def _load_meetings(self):
        session = get_session()
        try:
            meetings = get_meetings(session)
        finally:
            session.close()
        self._meeting_combo.blockSignals(True)
        self._meeting_combo.clear()
        self._meeting_combo.addItem("（会議を選択してください）", None)
        for m in meetings:
            scope = "全員" if not m.target_position_ids else "役職指定"
            self._meeting_combo.addItem(
                f"{m.date.strftime('%Y/%m/%d')}　{m.name}　（{scope}）", m.id)
        self._meeting_combo.blockSignals(False)
        if meetings:
            self._meeting_combo.setCurrentIndex(1)
        else:
            self._current_meeting_id = None

    def _on_meeting_select(self):
        self._current_meeting_id = self._meeting_combo.currentData()
        self._load_preentry()
        if self._inner.currentIndex() == 1:
            self._refresh_reception()

    def _on_inner_tab_change(self, idx: int):
        if idx == 1:
            self._refresh_reception()
            self._timer.start()
        else:
            self._timer.stop()

    def _create_meeting(self):
        session = get_session()
        try:
            positions = get_positions(session)
        finally:
            session.close()
        dlg = _NewMeetingDialog(positions, self)
        if dlg.exec():
            name, meeting_date, target_ids = dlg.get_values()
            session = get_session()
            try:
                create_meeting(session, name, meeting_date, target_ids)
            finally:
                session.close()
            self._load_meetings()

    def _delete_meeting(self):
        if not self._current_meeting_id:
            return
        ret = QMessageBox.question(
            self, "削除確認",
            f"会議「{self._meeting_combo.currentText()}」を削除しますか？\n"
            "出欠データもすべて削除されます。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if ret != QMessageBox.StandardButton.Yes:
            return
        session = get_session()
        try:
            delete_meeting(session, self._current_meeting_id)
        finally:
            session.close()
        self._current_meeting_id = None
        self._load_meetings()
