import json
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QWidget, QTableWidget, QTableWidgetItem,
    QHeaderView, QPushButton, QSplitter, QLabel
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from sqlalchemy.orm import Session
from app.services.member_service import get_member_history, get_member, member_to_snapshot

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

_HIGHLIGHT = QColor("#FEF3C7")   # 差分行: 黄色


class MemberHistoryDialog(QDialog):
    def __init__(self, session: Session, member_id: int, parent=None):
        super().__init__(parent)
        self._session = session
        self._member_id = member_id
        self._history = []
        member = get_member(session, member_id)
        self.setWindowTitle(
            f"変更履歴: {member.organization_name if member else ''}")
        self.resize(760, 560)
        self._build()
        self._load()

    def _build(self):
        layout = QVBoxLayout(self)
        splitter = QSplitter(Qt.Orientation.Vertical)

        # ── 上部: 履歴一覧テーブル ──
        self._table = QTableWidget(0, 3)
        self._table.setHorizontalHeaderLabels(["変更日時", "変更者", "変更理由"])
        self._table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.Stretch)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.currentItemChanged.connect(
            lambda cur, _: self._show_comparison(self._table.currentRow())
        )
        splitter.addWidget(self._table)

        # ── 下部: 対比テーブル ──
        bottom = QWidget()
        bl = QVBoxLayout(bottom)
        bl.setContentsMargins(0, 4, 0, 0)
        bl.setSpacing(4)

        self._compare_label = QLabel("履歴を選択すると、1つ前のデータとの対比を表示します")
        self._compare_label.setStyleSheet("color:#6B7280; font-size:11px;")
        bl.addWidget(self._compare_label)

        self._compare_table = QTableWidget(0, 3)
        self._compare_table.setHorizontalHeaderLabels(
            ["項目", "変更前", "変更後"])
        self._compare_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents)
        self._compare_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch)
        self._compare_table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.Stretch)
        self._compare_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._compare_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows)
        bl.addWidget(self._compare_table)

        splitter.addWidget(bottom)
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
            self._table.setItem(row, 1, QTableWidgetItem(h.changed_by or ""))
            self._table.setItem(row, 2, QTableWidgetItem(h.change_reason or ""))

    # ── ユーティリティ ──

    def _parse(self, snapshot_json: str) -> dict:
        try:
            return json.loads(snapshot_json) if snapshot_json else {}
        except Exception:
            return {}

    def _fmt(self, k: str, v) -> str:
        if k == "is_active":
            return "在任中" if v else "議員退任"
        if v is None or v == "":
            return "（なし）"
        return str(v)

    # ── 対比表示 ──

    def _show_comparison(self, row: int):
        self._compare_table.setRowCount(0)
        if row < 0 or row >= len(self._history):
            self._compare_label.setText(
                "履歴を選択すると、変更前後のデータの対比を表示します")
            return

        # スナップショットは「変更直前」の状態を記録している
        snap_before = self._parse(self._history[row].snapshot)
        ts_before = (self._history[row].changed_at.strftime("%Y/%m/%d %H:%M")
                     if self._history[row].changed_at else "")

        if row > 0:
            # 1つ新しい履歴の「変更直前」= この変更の結果
            snap_after = self._parse(self._history[row - 1].snapshot)
            ts_after = (self._history[row - 1].changed_at.strftime("%Y/%m/%d %H:%M")
                        if self._history[row - 1].changed_at else "")
        else:
            # 最新の変更: 現在のDB状態が「変更後」
            m = get_member(self._session, self._member_id)
            snap_after = self._parse(member_to_snapshot(m)) if m else {}
            ts_after = "現在"

        self._compare_label.setText(
            f"変更前: {ts_before}　→　変更後: {ts_after}　　※差分のある行を黄色で表示")

        # 通常フィールド
        for k, v_before in snap_before.items():
            if k == "email_addresses":
                continue
            label    = _FIELD_LABELS.get(k, k)
            s_before = self._fmt(k, v_before)
            s_after  = self._fmt(k, snap_after.get(k))
            self._add_row(label, s_before, s_after)

        # メールアドレス
        emails_before = snap_before.get("email_addresses", [])
        emails_after  = snap_after.get("email_addresses",  [])
        for i in range(max(len(emails_before), len(emails_after))):
            eb = emails_before[i] if i < len(emails_before) else {}
            ea = emails_after[i]  if i < len(emails_after)  else {}
            def _mail(e):
                a = e.get("address", "")
                lb = e.get("label", "")
                return f"{a}（{lb}）" if a else "（なし）"
            self._add_row(f"メール{i + 1}", _mail(eb), _mail(ea))

    def _add_row(self, label: str, s_old: str, s_new: str):
        r = self._compare_table.rowCount()
        self._compare_table.insertRow(r)
        self._compare_table.setItem(r, 0, QTableWidgetItem(label))
        self._compare_table.setItem(r, 1, QTableWidgetItem(s_old))
        self._compare_table.setItem(r, 2, QTableWidgetItem(s_new))
        if s_old != s_new:
            for c in range(3):
                self._compare_table.item(r, c).setBackground(_HIGHLIGHT)
