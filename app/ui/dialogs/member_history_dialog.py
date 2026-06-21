import json
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QPushButton, QTextEdit, QSplitter
)
from PyQt6.QtCore import Qt
from sqlalchemy.orm import Session
from app.services.member_service import get_member_history, get_member

_FIELD_LABELS = {
    "member_number":     "会員番号",
    "position_name":     "会議所役職",
    "organization_name": "事業所名",
    "organization_kana": "事業所名フリガナ",
    "title":             "役職名",
    "name":              "氏名",
    "name_kana":         "氏名フリガナ",
    "notes":             "備考",
    "is_active":         "議員状態",
    "position_id":       "会議所役職ID（旧）",
}


class MemberHistoryDialog(QDialog):
    def __init__(self, session: Session, member_id: int, parent=None):
        super().__init__(parent)
        self._session = session
        self._member_id = member_id
        self._history = []  # _build() でシグナル接続前に初期化
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
        self._snapshot_view.setPlaceholderText("行を選択するとその時点のデータを表示します")
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
            ts = h.changed_at.strftime("%Y/%m/%d %H:%M") if h.changed_at else ""
            self._table.setItem(row, 0, QTableWidgetItem(ts))
            self._table.setItem(row, 1, QTableWidgetItem(h.changed_by))
            self._table.setItem(row, 2, QTableWidgetItem(h.change_reason))

    def _show_snapshot(self, row: int):
        if row < 0 or row >= len(self._history):
            return
        snap = self._history[row].snapshot or ""
        try:
            data = json.loads(snap) if snap else {}
            lines = []
            for k, v in data.items():
                if k == "email_addresses":
                    continue
                label = _FIELD_LABELS.get(k, k)
                if k == "is_active":
                    v = "在任中" if v else "退任"
                elif v is None or v == "":
                    v = "（なし）"
                lines.append(f"{label}: {v}")
            emails = data.get("email_addresses", [])
            if emails:
                lines.append("")
                for i, e in enumerate(emails, 1):
                    addr = e.get("address", "")
                    lbl = e.get("label", "")
                    lines.append(f"メール{i}: {addr}" + (f"（{lbl}）" if lbl else ""))
            self._snapshot_view.setPlainText("\n".join(lines))
        except Exception:
            self._snapshot_view.setPlainText(snap or "")
