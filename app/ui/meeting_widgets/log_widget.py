from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QPushButton,
)
from app.database.connection import get_session
from app.services.reception_log_service import get_logs
from app.services.settings_service import get_font_size, set_font_size


class LogWidget(QWidget):
    def __init__(self):
        super().__init__()
        self._build()

    def load(self, meeting_id: int | None):
        self._meeting_id = meeting_id
        self._load_logs()

    def _build(self):
        layout = QVBoxLayout(self)

        btn_row = QHBoxLayout()
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

        _log_headers = ["日時", "担当者", "事業所名", "変更前", "変更後"]
        self._log_table = QTableWidget(0, 5)
        self._log_table.setHorizontalHeaderLabels(_log_headers)
        h = self._log_table.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        h.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        from app.ui.widgets.table_header_style import style_table_header
        style_table_header(self._log_table)
        from app.ui.widgets.column_visibility import setup_column_visibility_menu
        setup_column_visibility_menu(
            self._log_table, _log_headers, "log_table", self)
        self._log_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._log_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        _sys_pt = self._log_table.font().pointSize()
        _saved_pt = get_font_size("log_tab", _sys_pt)
        _f = self._log_table.font()
        _f.setPointSize(_saved_pt)
        self._log_table.setFont(_f)
        self._log_table.verticalHeader().setDefaultSectionSize(
            self._log_table.verticalHeader().defaultSectionSize()
            + (_saved_pt - _sys_pt) * 2)
        layout.addWidget(self._log_table)
        self._meeting_id: int | None = None

    def _adjust_font(self, delta: int):
        f = self._log_table.font()
        new_size = max(6, f.pointSize() + delta)
        f.setPointSize(new_size)
        self._log_table.setFont(f)
        vh = self._log_table.verticalHeader()
        vh.setDefaultSectionSize(max(20, vh.defaultSectionSize() + delta * 2))
        set_font_size("log_tab", new_size)

    def _load_logs(self):
        if not self._meeting_id:
            self._log_table.setRowCount(0)
            return
        session = get_session()
        try:
            logs = get_logs(session, self._meeting_id)
        finally:
            session.close()
        self._log_table.setRowCount(0)
        for log in logs:
            row = self._log_table.rowCount()
            self._log_table.insertRow(row)
            org = log.member.organization_name if log.member else ""
            cells = [
                log.changed_at.strftime("%Y/%m/%d %H:%M:%S"),
                log.staff_name,
                org,
                log.old_status or "（未受付）",
                log.new_status or "（未受付）",
            ]
            for col, val in enumerate(cells):
                self._log_table.setItem(row, col, QTableWidgetItem(val))
