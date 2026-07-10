from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QPushButton, QLabel, QLineEdit, QComboBox, QApplication, QSizePolicy,
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QPixmap, QFont
from app.database.connection import get_session
from app.services.meeting_service import get_attendance_data, get_reception_summary, update_actual_status
from app.services.reception_log_service import create_log
from app.services.settings_service import get_font_size, set_font_size
from app.utils import to_katakana
from app.ui.meeting_widgets import count_label

_STATUS_COLORS = {
    "出席": "#DCFCE7",
    "代理": "#DBEAFE",
    "委任": "#FEF9C3",
    "欠席": "#FEE2E2",
}
_ACTUAL_OPTIONS = ["", "出席", "代理", "委任", "欠席"]


class _NoWheelComboBox(QComboBox):
    def wheelEvent(self, event):
        event.ignore()


class _ReceptionTable(QTableWidget):
    def mousePressEvent(self, event):
        if QApplication.activePopupWidget() is not None:
            return
        super().mousePressEvent(event)


class ReceptionWidget(QWidget):
    def __init__(self, staff_name: str = "", readonly: bool = False):
        super().__init__()
        self._staff_name = staff_name
        self._readonly = readonly
        self._meeting_id: int | None = None
        self._rec_data: list[dict] = []
        self._build()
        self._timer = QTimer()
        self._timer.setInterval(3000)
        self._timer.timeout.connect(self._refresh_reception)
        self._export_timer = QTimer()
        self._export_timer.setSingleShot(True)
        self._export_timer.setInterval(500)
        self._export_timer.timeout.connect(self._do_export_html)

    def load(self, meeting_id: int | None):
        self._meeting_id = meeting_id
        self._load_reception()

    def start_timer(self):
        self._timer.start()

    def stop_timer(self):
        self._timer.stop()

    # ─── UI構築 ────────────────────────────────────────────

    def _build(self):
        layout = QVBoxLayout(self)

        count_grp = QGroupBox("当日受付集計（3秒ごと自動更新）")
        count_layout = QHBoxLayout(count_grp)
        self._lbl_attend   = count_label("出席: 0",   "#16A34A")
        self._lbl_proxy    = count_label("代理: 0",   "#2563EB")
        self._lbl_delegate = count_label("委任: 0",   "#CA8A04")
        self._lbl_absent   = count_label("欠席: 0",   "#DC2626")
        self._lbl_pending  = count_label("未受付: 0", "#6B7280")
        self._lbl_total    = count_label("合計: 0",   "#1E40AF", bold=True)
        for lbl in [self._lbl_attend, self._lbl_proxy, self._lbl_delegate,
                    self._lbl_absent, self._lbl_pending, self._lbl_total]:
            count_layout.addWidget(lbl)
        count_layout.addStretch()
        layout.addWidget(count_grp)

        search_row = QHBoxLayout()
        lbl_search = QLabel("検索:")
        lbl_search.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        search_row.addWidget(lbl_search)
        search_row.addStretch(1)
        self._search = QLineEdit()
        self._search.setPlaceholderText("事業所名・氏名・会員番号")
        self._search.textChanged.connect(self._filter_reception)
        _sf = self._search.font()
        _sf.setPointSize(_sf.pointSize() + 3)
        self._search.setFont(_sf)
        self._search.setMinimumHeight(self._search.sizeHint().height() * 2)
        from app.ui.widgets.search_style import style_search_input
        style_search_input(self._search, max_width=320)
        search_row.addWidget(self._search, 2)
        search_row.addStretch(1)
        btn_font_down = QPushButton("A-")
        btn_font_down.setFixedWidth(36)
        btn_font_down.setToolTip("文字を小さくする")
        btn_font_down.clicked.connect(lambda: self._adjust_rec_font(-1))
        btn_font_up = QPushButton("A+")
        btn_font_up.setFixedWidth(36)
        btn_font_up.setToolTip("文字を大きくする")
        btn_font_up.clicked.connect(lambda: self._adjust_rec_font(1))
        search_row.addWidget(btn_font_down)
        search_row.addWidget(btn_font_up)
        layout.addLayout(search_row)

        body_row = QHBoxLayout()
        body_row.setSpacing(6)

        photo_w = QWidget()
        photo_w.setFixedWidth(112)
        photo_vl = QVBoxLayout(photo_w)
        photo_vl.setContentsMargins(0, 0, 4, 0)
        photo_vl.setSpacing(2)
        self._rec_photo_label = QLabel()
        self._rec_photo_label.setFixedSize(96, 120)
        self._rec_photo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._rec_photo_label.setStyleSheet(
            "border: 1px solid #D1D5DB; background: #F9FAFB; color: #9CA3AF;")
        self._rec_photo_label.setText("写真なし")
        self._rec_name_label = QLabel("")
        self._rec_name_label.setWordWrap(True)
        self._rec_name_label.setFixedWidth(106)
        self._rec_name_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self._rec_name_label.setStyleSheet("font-size: 10px; color: #374151;")
        photo_vl.addWidget(self._rec_photo_label)
        photo_vl.addWidget(self._rec_name_label)
        photo_vl.addStretch()
        body_row.addWidget(photo_w)

        _rec_headers = ["会員番号", "事業所名", "会議所役職", "氏名", "事前", "当日受付", "代理情報"]
        self._rec_table = _ReceptionTable(0, 7)
        self._rec_table.setHorizontalHeaderLabels(_rec_headers)
        h = self._rec_table.horizontalHeader()
        h.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        from app.ui.widgets.table_header_style import style_table_header
        style_table_header(self._rec_table)
        from app.ui.widgets.column_visibility import setup_column_visibility_menu
        setup_column_visibility_menu(
            self._rec_table, _rec_headers, "reception_table", self)
        self._rec_table.setColumnWidth(0, 80)
        self._rec_table.setColumnWidth(1, 200)
        self._rec_table.setColumnWidth(2, 120)
        self._rec_table.setColumnWidth(3, 100)
        self._rec_table.setColumnWidth(4, 70)
        self._rec_table.setColumnWidth(5, 90)
        self._rec_table.setColumnWidth(6, 160)
        self._rec_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._rec_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._rec_table.currentCellChanged.connect(
            lambda row, _col, _pr, _pc: self._update_reception_photo(row))
        _sys_pt = self._rec_table.font().pointSize()
        _saved_pt = get_font_size("reception_tab", _sys_pt + 3)
        _f = self._rec_table.font()
        _f.setPointSize(_saved_pt)
        self._rec_table.setFont(_f)
        _base_row = self._rec_table.verticalHeader().defaultSectionSize()
        self._rec_table.verticalHeader().setDefaultSectionSize(
            _base_row + (_saved_pt - _sys_pt) * 2)
        body_row.addWidget(self._rec_table, 1)
        layout.addLayout(body_row, 1)

    # ─── データ操作 ────────────────────────────────────────

    def _load_reception(self):
        if not self._meeting_id:
            return
        session = get_session()
        try:
            self._rec_data = get_attendance_data(session, self._meeting_id)
            for d in self._rec_data:
                if d["status"] == "委任" and not d.get("actual_status"):
                    update_actual_status(
                        session, self._meeting_id, d["member_id"], "委任")
                    d["actual_status"] = "委任"
            summary = get_reception_summary(session, self._meeting_id)
        finally:
            session.close()

        self._update_rec_summary(summary)

        scrollbar = self._rec_table.verticalScrollBar()
        scroll_pos = scrollbar.value()
        self._rec_table.setUpdatesEnabled(False)
        self._rec_table.setRowCount(0)
        for d in self._rec_data:
            row = self._rec_table.rowCount()
            self._rec_table.insertRow(row)
            proxy_info = ""
            if d["status"] == "代理" or d.get("actual_status") == "代理":
                proxy_info = " ".join(
                    p for p in [d["proxy_title"], d["proxy_name"]] if p)
            effective = d.get("actual_status") or d["status"]
            bg = _STATUS_COLORS.get(effective)
            for col, val in enumerate([d["member_number"], d["org_name"],
                                       d["position"], d["name"], d["status"]]):
                item = QTableWidgetItem(val)
                if bg:
                    item.setBackground(QColor(bg))
                if col == 0:
                    item.setData(Qt.ItemDataRole.UserRole, d["member_id"])
                self._rec_table.setItem(row, col, item)
            actual = d.get("actual_status") or ""
            if self._readonly:
                item5 = QTableWidgetItem(actual)
                if bg:
                    item5.setBackground(QColor(bg))
                self._rec_table.setItem(row, 5, item5)
            else:
                combo = _NoWheelComboBox()
                combo.addItems(_ACTUAL_OPTIONS)
                combo.blockSignals(True)
                combo.setCurrentText(actual)
                combo.blockSignals(False)
                mid = d["member_id"]
                combo.currentTextChanged.connect(
                    lambda text, m=mid: self._save_actual_status(m, text))
                self._rec_table.setCellWidget(row, 5, combo)
            item6 = QTableWidgetItem(proxy_info)
            if bg:
                item6.setBackground(QColor(bg))
            self._rec_table.setItem(row, 6, item6)
        self._rec_table.setUpdatesEnabled(True)
        scrollbar.setValue(scroll_pos)
        self._filter_reception()

    def _refresh_reception(self):
        if not self._meeting_id:
            return
        session = get_session()
        try:
            new_data = get_attendance_data(session, self._meeting_id)
            summary = get_reception_summary(session, self._meeting_id)
        finally:
            session.close()

        self._update_rec_summary(summary)

        if len(new_data) != self._rec_table.rowCount():
            self._rec_data = new_data
            self._load_reception()
            return

        self._rec_data = new_data
        for row, d in enumerate(new_data):
            effective = d.get("actual_status") or d["status"]
            bg = _STATUS_COLORS.get(effective)
            qbg = QColor(bg) if bg else None
            for col in [0, 1, 2, 3, 4, 6]:
                item = self._rec_table.item(row, col)
                if item:
                    if qbg:
                        item.setBackground(qbg)
                    else:
                        item.setData(Qt.ItemDataRole.BackgroundRole, None)
            new_val = d.get("actual_status") or ""
            if self._readonly:
                item5 = self._rec_table.item(row, 5)
                if item5 and item5.text() != new_val:
                    item5.setText(new_val)
                    if qbg:
                        item5.setBackground(qbg)
            else:
                combo = self._rec_table.cellWidget(row, 5)
                if combo and combo.currentText() != new_val:
                    combo.blockSignals(True)
                    combo.setCurrentText(new_val)
                    combo.blockSignals(False)
        self._filter_reception()

    def _update_rec_summary(self, summary: dict):
        self._lbl_attend.setText(f"出席: {summary['出席']}")
        self._lbl_proxy.setText(f"代理: {summary['代理']}")
        self._lbl_delegate.setText(f"委任: {summary['委任']}")
        self._lbl_absent.setText(f"欠席: {summary['欠席']}")
        self._lbl_pending.setText(f"未受付: {summary['未受付']}")
        self._lbl_total.setText(f"合計: {summary['合計']}")

    def _save_actual_status(self, member_id: int, actual_status: str):
        if not self._meeting_id:
            return
        session = get_session()
        try:
            old = next(
                (d.get("actual_status") or "" for d in self._rec_data
                 if d["member_id"] == member_id), "")
            update_actual_status(session, self._meeting_id, member_id, actual_status)
            if self._staff_name:
                create_log(session, self._meeting_id, member_id,
                           self._staff_name, old, actual_status)
        finally:
            session.close()
        self._export_html_silent()

    def _export_html_silent(self):
        self._export_timer.start()

    def _do_export_html(self):
        from app.utils.app_config import get_html_export_path
        path = get_html_export_path()
        if not path:
            return
        try:
            from app.services.html_export_service import export_attendance_html
            export_attendance_html(path)
        except Exception:
            pass

    def _filter_reception(self):
        keyword = to_katakana(self._search.text().strip())
        for row in range(self._rec_table.rowCount()):
            if not keyword:
                self._rec_table.setRowHidden(row, False)
                continue
            if row >= len(self._rec_data):
                self._rec_table.setRowHidden(row, False)
                continue
            d = self._rec_data[row]
            visible = (
                keyword in to_katakana(d.get("org_name", ""))
                or keyword in to_katakana(d.get("org_kana", ""))
                or keyword in to_katakana(d.get("name", ""))
                or keyword in d.get("member_number", "")
                or keyword in to_katakana(d.get("position", ""))
            )
            self._rec_table.setRowHidden(row, not visible)

    def _adjust_rec_font(self, delta: int):
        f = self._rec_table.font()
        new_size = max(6, f.pointSize() + delta)
        f.setPointSize(new_size)
        self._rec_table.setFont(f)
        vh = self._rec_table.verticalHeader()
        vh.setDefaultSectionSize(max(20, vh.defaultSectionSize() + delta * 2))
        set_font_size("reception_tab", new_size)

    def _update_reception_photo(self, row: int):
        if row < 0:
            self._rec_photo_label.setText("写真なし")
            self._rec_photo_label.setPixmap(QPixmap())
            self._rec_name_label.clear()
            return
        item = self._rec_table.item(row, 0)
        if not item:
            return
        member_id = item.data(Qt.ItemDataRole.UserRole)
        if not member_id:
            return
        session = get_session()
        try:
            from app.database.models import Member
            from app.services.photo_service import bytes_to_pixmap
            m = session.get(Member, member_id)
            if m and m.photo_full:
                pix = bytes_to_pixmap(m.photo_full)
                if pix:
                    pix = pix.scaled(96, 120,
                                     Qt.AspectRatioMode.KeepAspectRatio,
                                     Qt.TransformationMode.SmoothTransformation)
                    self._rec_photo_label.setPixmap(pix)
                    self._rec_photo_label.setText("")
                else:
                    self._rec_photo_label.clear()
                    self._rec_photo_label.setText("写真なし")
            else:
                self._rec_photo_label.clear()
                self._rec_photo_label.setText("写真なし")
            if m:
                self._rec_name_label.setText(f"{m.organization_name}\n{m.name}")
            else:
                self._rec_name_label.clear()
        finally:
            session.close()
