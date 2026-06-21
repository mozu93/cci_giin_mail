# app/ui/meeting_tab.py
from datetime import date
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QPushButton, QLabel, QLineEdit, QComboBox,
    QDialog, QFormLayout, QDateEdit, QMessageBox,
    QFileDialog, QTabWidget
)
from PyQt6.QtCore import Qt, QTimer, QDate
from PyQt6.QtGui import QColor
from app.database.connection import get_session
from app.services.meeting_service import (
    STATUS_OPTIONS, create_meeting, get_meetings, delete_meeting,
    upsert_attendance, get_attendance_data, get_summary, export_csv
)

_STATUS_COLORS = {
    "出席": "#DCFCE7",
    "代理": "#DBEAFE",
    "委任": "#FEF9C3",
    "欠席": "#FEE2E2",
}


class _NewMeetingDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("会議作成")
        self.setFixedWidth(320)
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
        self.accept()

    def get_values(self) -> tuple[str, date]:
        d = self._date.date()
        return self._name.text().strip(), date(d.year(), d.month(), d.day())


class MeetingTab(QWidget):
    def __init__(self):
        super().__init__()
        self._current_meeting_id: int | None = None
        self._preentry_data: list[dict] = []
        self._rec_data: list[dict] = []
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
        btn_row = QHBoxLayout()
        btn_csv = QPushButton("CSV出力")
        btn_csv.clicked.connect(self._export_csv)
        btn_row.addStretch()
        btn_row.addWidget(btn_csv)
        layout.addLayout(btn_row)

        self._pre_table = QTableWidget(0, 6)
        self._pre_table.setHorizontalHeaderLabels(
            ["会員番号", "事業所名", "氏名", "ステータス", "代理役職名", "代理氏名"])
        h = self._pre_table.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        h.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(4, QHeaderView.ResizeMode.Interactive)
        h.setSectionResizeMode(5, QHeaderView.ResizeMode.Interactive)
        self._pre_table.setColumnWidth(4, 120)
        self._pre_table.setColumnWidth(5, 120)
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

        self._pre_table.setUpdatesEnabled(False)
        for i, d in enumerate(self._preentry_data):
            self._pre_table.insertRow(i)
            self._pre_table.setItem(i, 0, QTableWidgetItem(d["member_number"]))
            self._pre_table.setItem(i, 1, QTableWidgetItem(d["org_name"]))
            self._pre_table.setItem(i, 2, QTableWidgetItem(d["name"]))

            combo = QComboBox()
            combo.addItems(STATUS_OPTIONS)
            combo.setCurrentText(d["status"])
            combo.currentTextChanged.connect(
                lambda text, row=i: self._on_status_change(row, text))
            self._pre_table.setCellWidget(i, 3, combo)

            is_proxy = d["status"] == "代理"
            title_edit = QLineEdit(d["proxy_title"])
            name_edit = QLineEdit(d["proxy_name"])
            title_edit.setEnabled(is_proxy)
            name_edit.setEnabled(is_proxy)
            title_edit.editingFinished.connect(
                lambda row=i: self._save_proxy(row))
            name_edit.editingFinished.connect(
                lambda row=i: self._save_proxy(row))
            self._pre_table.setCellWidget(i, 4, title_edit)
            self._pre_table.setCellWidget(i, 5, name_edit)
        self._pre_table.setUpdatesEnabled(True)

    def _on_status_change(self, row: int, text: str):
        if row >= len(self._preentry_data):
            return
        d = self._preentry_data[row]
        d["status"] = text
        title_edit = self._pre_table.cellWidget(row, 4)
        name_edit = self._pre_table.cellWidget(row, 5)
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

    def _save_proxy(self, row: int):
        if row >= len(self._preentry_data):
            return
        d = self._preentry_data[row]
        title_edit = self._pre_table.cellWidget(row, 4)
        name_edit = self._pre_table.cellWidget(row, 5)
        d["proxy_title"] = title_edit.text().strip() if title_edit else ""
        d["proxy_name"] = name_edit.text().strip() if name_edit else ""
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

        # 集計バー
        count_grp = QGroupBox("出欠集計（3秒ごと自動更新）")
        count_layout = QHBoxLayout(count_grp)
        self._lbl_attend   = self._count_label("出席: 0", "#16A34A")
        self._lbl_proxy    = self._count_label("代理: 0", "#2563EB")
        self._lbl_delegate = self._count_label("委任: 0", "#CA8A04")
        self._lbl_absent   = self._count_label("欠席: 0", "#DC2626")
        self._lbl_total    = self._count_label("合計: 0", "#1E40AF", bold=True)
        for lbl in [self._lbl_attend, self._lbl_proxy,
                    self._lbl_delegate, self._lbl_absent, self._lbl_total]:
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

        # 一覧
        self._rec_table = QTableWidget(0, 6)
        self._rec_table.setHorizontalHeaderLabels(
            ["会員番号", "事業所名", "会議所役職", "氏名", "ステータス", "代理情報"])
        h = self._rec_table.horizontalHeader()
        h.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        h.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
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

    def _refresh_reception(self):
        if not self._current_meeting_id:
            return
        session = get_session()
        try:
            self._rec_data = get_attendance_data(
                session, self._current_meeting_id)
            summary = get_summary(session, self._current_meeting_id)
        finally:
            session.close()

        self._lbl_attend.setText(f"出席: {summary['出席']}")
        self._lbl_proxy.setText(f"代理: {summary['代理']}")
        self._lbl_delegate.setText(f"委任: {summary['委任']}")
        self._lbl_absent.setText(f"欠席: {summary['欠席']}")
        self._lbl_total.setText(f"合計: {summary['合計']}")

        scrollbar = self._rec_table.verticalScrollBar()
        scroll_pos = scrollbar.value()
        self._rec_table.setUpdatesEnabled(False)
        self._rec_table.setRowCount(0)
        for d in self._rec_data:
            row = self._rec_table.rowCount()
            self._rec_table.insertRow(row)
            proxy_info = ""
            if d["status"] == "代理":
                proxy_info = " ".join(
                    p for p in [d["proxy_title"], d["proxy_name"]] if p)
            cells = [d["member_number"], d["org_name"], d["position"],
                     d["name"], d["status"], proxy_info]
            bg = _STATUS_COLORS.get(d["status"])
            for col, val in enumerate(cells):
                item = QTableWidgetItem(val)
                if bg:
                    item.setBackground(QColor(bg))
                self._rec_table.setItem(row, col, item)
        self._rec_table.setUpdatesEnabled(True)
        scrollbar.setValue(scroll_pos)
        self._filter_reception()

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
            self._meeting_combo.addItem(
                f"{m.date.strftime('%Y/%m/%d')}　{m.name}", m.id)
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
        dlg = _NewMeetingDialog(self)
        if dlg.exec():
            name, meeting_date = dlg.get_values()
            session = get_session()
            try:
                create_meeting(session, name, meeting_date)
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
