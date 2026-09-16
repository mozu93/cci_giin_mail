from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QPushButton, QLabel,
)
from sqlalchemy.orm import Session
from app.services.member_service import get_recent_changes

_INITIAL_COUNT = 10
_MAX_COUNT = 30


class RecentChangesDialog(QDialog):
    """全会員の直近の変更内容を横断して一覧表示するダイアログ。
    はじめは直近10件、「もっと表示」で最大30件まで表示する。"""

    def __init__(self, session: Session, parent=None):
        super().__init__(parent)
        self.setWindowTitle("最近の更新")
        self.resize(760, 520)
        self._events = get_recent_changes(session, limit=_MAX_COUNT)
        self._shown_count = _INITIAL_COUNT
        self._build()
        self._render()

    def _build(self):
        layout = QVBoxLayout(self)

        self._info_label = QLabel("")
        self._info_label.setStyleSheet("color:#6B7280; font-size:11px;")
        layout.addWidget(self._info_label)

        self._table = QTableWidget(0, 6)
        self._table.setHorizontalHeaderLabels(
            ["変更日時", "事業所名", "項目", "変更前", "変更後", "変更者"])
        h = self._table.horizontalHeader()
        h.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        h.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        h.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self._table.setColumnWidth(0, 130)
        self._table.setColumnWidth(1, 160)
        self._table.setColumnWidth(2, 90)
        self._table.setColumnWidth(5, 100)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        layout.addWidget(self._table)

        btn_row = QHBoxLayout()
        self._btn_more = QPushButton("もっと表示（最大30件）")
        self._btn_more.clicked.connect(self._show_more)
        btn_row.addWidget(self._btn_more)
        btn_row.addStretch()
        btn_close = QPushButton("閉じる")
        btn_close.clicked.connect(self.accept)
        btn_row.addWidget(btn_close)
        layout.addLayout(btn_row)

    def _show_more(self):
        self._shown_count = _MAX_COUNT
        self._render()

    def _render(self):
        events = self._events[:self._shown_count]
        self._table.setRowCount(0)
        for event in events:
            ts = (event["changed_at"].strftime("%Y/%m/%d %H:%M")
                 if event["changed_at"] else "")
            for change in event["changes"]:
                row = self._table.rowCount()
                self._table.insertRow(row)
                self._table.setItem(row, 0, QTableWidgetItem(ts))
                self._table.setItem(row, 1, QTableWidgetItem(event["org_name"]))
                self._table.setItem(row, 2, QTableWidgetItem(change["field"]))
                self._table.setItem(row, 3, QTableWidgetItem(change["old"]))
                self._table.setItem(row, 4, QTableWidgetItem(change["new"]))
                self._table.setItem(row, 5, QTableWidgetItem(event["changed_by"]))

        total = len(self._events)
        shown = min(self._shown_count, total)
        self._info_label.setText(f"直近の変更 {shown}件（最大{_MAX_COUNT}件まで）を表示しています")
        self._btn_more.setVisible(shown < total and self._shown_count < _MAX_COUNT)
