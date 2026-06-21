# app/ui/dialogs/member_history_dialog.py
import json
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QPushButton, QTextEdit, QSplitter, QLabel
)
from PyQt6.QtCore import Qt
from sqlalchemy.orm import Session
from app.services.member_service import get_member_history, get_member


class MemberHistoryDialog(QDialog):
    def __init__(self, session: Session, member_id: int, parent=None):
        super().__init__(parent)
        self._session = session
        self._member_id = member_id
        member = get_member(session, member_id)
        self.setWindowTitle(f"変更履歴: {member.organization_name if member else ''}")
        self.resize(700, 500)
        self._build()
        self._load()

    def _build(self):
        layout = QVBoxLayout(self)
        splitter = QSplitter(Qt.Orientation.Vertical)

        self._table = QTableWidget(0, 3)
        self._table.setHorizontalHeaderLabels(["変更日時", "変更者", "変更理由"])
        self._table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.Stretch)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.currentRowChanged.connect(self._show_snapshot)
        splitter.addWidget(self._table)

        self._snapshot_view = QTextEdit()
        self._snapshot_view.setReadOnly(True)
        self._snapshot_view.setPlaceholderText("行を選択すると変更前のデータを表示します")
        splitter.addWidget(self._snapshot_view)

        layout.addWidget(splitter)

        btn_close = QPushButton("閉じる")
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close)

    def _load(self):
        self._history = get_member_history(self._session, self._member_id)
        self._table.setRowCount(0)
        for h in self._history:
            row = self._table.rowCount()
            self._table.insertRow(row)
            self._table.setItem(row, 0, QTableWidgetItem(
                h.changed_at.strftime("%Y/%m/%d %H:%M")))
            self._table.setItem(row, 1, QTableWidgetItem(h.changed_by))
            self._table.setItem(row, 2, QTableWidgetItem(h.change_reason))

    def _show_snapshot(self, row: int):
        if row < 0 or row >= len(self._history):
            return
        snap = self._history[row].snapshot
        try:
            data = json.loads(snap)
            lines = [f"{k}: {v}" for k, v in data.items() if k != "email_addresses"]
            emails = data.get("email_addresses", [])
            for i, e in enumerate(emails, 1):
                lines.append(f"メール{i}: {e['address']} ({e['label']})")
            self._snapshot_view.setPlainText("\n".join(lines))
        except Exception:
            self._snapshot_view.setPlainText(snap)
