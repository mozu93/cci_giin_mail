# app/ui/dialogs/attach_confirm_dialog.py
import os
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QPushButton, QHBoxLayout, QLabel, QMessageBox
)
from PyQt6.QtGui import QColor


class AttachConfirmDialog(QDialog):
    def __init__(self, member_attach_list: list[dict], parent=None):
        super().__init__(parent)
        self.setWindowTitle("個別添付ファイル確認")
        self.resize(750, 500)
        self._list = member_attach_list
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        missing = sum(1 for r in self._list if not r["found"])
        if missing:
            layout.addWidget(QLabel(
                f"ファイルが見つからない企業が {missing} 件あります（×印）。\n"
                "「スキップして続行」を選ぶと、×印の企業は添付なしで送信されます。"
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
            fname = os.path.basename(r["filepath"]) if r["filepath"] else "-"
            self._table.setItem(row, 3, QTableWidgetItem(fname))
            found_item = QTableWidgetItem("○" if r["found"] else "×")
            if not r["found"]:
                found_item.setForeground(QColor("red"))
            self._table.setItem(row, 4, found_item)

        btn_row = QHBoxLayout()
        btn_cancel = QPushButton("中止")
        btn_cancel.clicked.connect(self.reject)
        btn_skip = QPushButton("スキップして続行（×印は添付なし）")
        btn_skip.clicked.connect(self.accept)
        btn_row.addWidget(btn_cancel)
        btn_row.addStretch()
        btn_row.addWidget(btn_skip)
        layout.addLayout(btn_row)

    def get_approved_list(self) -> list[dict]:
        return self._list
