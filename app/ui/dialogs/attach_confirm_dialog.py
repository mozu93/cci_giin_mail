# app/ui/dialogs/attach_confirm_dialog.py
import os
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QPushButton, QHBoxLayout, QLabel
)
from PyQt6.QtGui import QColor


class AttachConfirmDialog(QDialog):
    def __init__(self, member_attach_list: list[dict], parent=None):
        super().__init__(parent)
        self.setWindowTitle("会社別添付ファイル 確認・設定")
        self.resize(750, 500)
        self._list = member_attach_list
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)

        found = sum(1 for r in self._list if r["found"])
        missing = len(self._list) - found

        summary = f"対象: {len(self._list)} 件　○ファイルあり: {found} 件　×ファイルなし: {missing} 件"
        layout.addWidget(QLabel(summary))

        if missing:
            warn = QLabel("× の企業はファイルが見つかりません。確定すると添付なしで送信されます。")
            warn.setStyleSheet("color: #DC2626;")
            layout.addWidget(warn)

        layout.addWidget(QLabel(
            "内容を確認して「確定」を押すと添付設定が保存されます。\n"
            "「キャンセル」を押すと添付設定はクリアされます。"
        ))

        self._table = QTableWidget(0, 5)
        self._table.setHorizontalHeaderLabels(
            ["事業所名", "会員番号", "送信先アドレス", "対応ファイル名", "確認"])
        self._table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self._table)

        for r in self._list:
            row = self._table.rowCount()
            self._table.insertRow(row)
            self._table.setItem(row, 0, QTableWidgetItem(r["org_name"]))
            self._table.setItem(row, 1, QTableWidgetItem(r["member_number"]))
            self._table.setItem(row, 2, QTableWidgetItem(r["to_address"]))
            filepaths = r["filepaths"]
            fname = ", ".join(os.path.basename(p) for p in filepaths) if filepaths else "-"
            self._table.setItem(row, 3, QTableWidgetItem(fname))
            found_item = QTableWidgetItem("○" if r["found"] else "×")
            if not r["found"]:
                found_item.setForeground(QColor("#DC2626"))
            self._table.setItem(row, 4, found_item)

        btn_row = QHBoxLayout()
        btn_cancel = QPushButton("キャンセル（添付をクリア）")
        btn_cancel.clicked.connect(self.reject)
        btn_ok = QPushButton("確定（設定を保存）")
        btn_ok.setStyleSheet("font-weight: bold;")
        btn_ok.clicked.connect(self.accept)
        btn_row.addWidget(btn_cancel)
        btn_row.addStretch()
        btn_row.addWidget(btn_ok)
        layout.addLayout(btn_row)
