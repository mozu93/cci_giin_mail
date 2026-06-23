from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QPushButton, QMessageBox
)
from PyQt6.QtCore import Qt
from sqlalchemy.orm import Session
from app.services.member_service import get_import_batches, revert_import_batch


class ImportRevertDialog(QDialog):
    def __init__(self, session: Session, parent=None):
        super().__init__(parent)
        self._session = session
        self.setWindowTitle("インポート取り消し")
        self.setMinimumWidth(560)
        self.setMinimumHeight(300)
        self._build()
        self._load()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("取り消したいインポートを選択してください。"))

        self._table = QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels(["日時", "担当者", "件数", "バッチID"])
        h = self._table.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._table.setColumnHidden(3, True)
        layout.addWidget(self._table)

        btn_row = QHBoxLayout()
        btn_cancel = QPushButton("閉じる")
        btn_cancel.clicked.connect(self.reject)
        self._btn_revert = QPushButton("選択したインポートを取り消す")
        self._btn_revert.setEnabled(False)
        self._btn_revert.setStyleSheet(
            "font-weight: bold; background-color: #DC2626; color: white;")
        self._btn_revert.clicked.connect(self._revert)
        self._table.itemSelectionChanged.connect(
            lambda: self._btn_revert.setEnabled(
                len(self._table.selectedItems()) > 0))
        btn_row.addWidget(btn_cancel)
        btn_row.addStretch()
        btn_row.addWidget(self._btn_revert)
        layout.addLayout(btn_row)

    def _load(self):
        self._table.setRowCount(0)
        batches = get_import_batches(self._session)
        for b in batches:
            row = self._table.rowCount()
            self._table.insertRow(row)
            dt = b.imported_at.strftime("%Y/%m/%d %H:%M") if b.imported_at else ""
            self._table.setItem(row, 0, QTableWidgetItem(dt))
            self._table.setItem(row, 1, QTableWidgetItem(b.imported_by or ""))
            count_item = QTableWidgetItem(f"{b.count}件")
            count_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._table.setItem(row, 2, count_item)
            self._table.setItem(row, 3, QTableWidgetItem(b.import_batch_id))
        if self._table.rowCount() == 0:
            self._table.setRowCount(1)
            item = QTableWidgetItem("取り消せるインポートはありません")
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self._table.setItem(0, 0, item)
            self._table.setSpan(0, 0, 1, 4)

    def _revert(self):
        row = self._table.currentRow()
        batch_id = self._table.item(row, 3)
        if batch_id is None:
            return
        batch_id = batch_id.text()
        dt = self._table.item(row, 0).text()
        by = self._table.item(row, 1).text()
        count = self._table.item(row, 2).text()

        ret = QMessageBox.warning(
            self, "取り消し確認",
            f"以下のインポートを取り消しますか？\n\n"
            f"日時: {dt}\n担当者: {by}\n変更件数: {count}\n\n"
            "・インポートで新規追加された会員は削除されます\n"
            "・インポートで更新された会員は変更前の状態に戻ります\n\n"
            "この操作は元に戻せません。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if ret != QMessageBox.StandardButton.Yes:
            return

        result = revert_import_batch(self._session, batch_id)
        QMessageBox.information(
            self, "取り消し完了",
            f"取り消しが完了しました。\n\n"
            f"削除（新規追加分）: {result['deleted']}件\n"
            f"復元（更新分）: {result['reverted']}件"
        )
        self.accept()
