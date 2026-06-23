from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem, QHeaderView,
)
from app.database.connection import get_session
from app.services.reception_log_service import get_logs


class LogWidget(QWidget):
    def __init__(self):
        super().__init__()
        self._build()

    def load(self, meeting_id: int | None):
        self._meeting_id = meeting_id
        self._load_logs()

    def _build(self):
        layout = QVBoxLayout(self)
        self._log_table = QTableWidget(0, 5)
        self._log_table.setHorizontalHeaderLabels(
            ["日時", "担当者", "事業所名", "変更前", "変更後"])
        h = self._log_table.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        h.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self._log_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._log_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        layout.addWidget(self._log_table)
        self._meeting_id: int | None = None

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
