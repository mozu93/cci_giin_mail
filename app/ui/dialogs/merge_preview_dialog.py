# app/ui/dialogs/merge_preview_dialog.py
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QPushButton, QLabel, QHBoxLayout, QFileDialog,
    QMessageBox
)
from app.services.import_service import load_member_file

_COL_KEYS = ["col1", "col2", "col3", "col4", "col5"]


class MergePreviewDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("差し込みデータ設定")
        self.resize(700, 500)
        self._merge_data: dict[str, dict] = {}
        self._col_names: list[str] = []
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            "差し込みデータCSV/ExcelをインポートしてCol1〜Col5に対応させます。\n"
            "「会員番号」列が必須です（名簿との突合キー）。"
        ))

        btn_row = QHBoxLayout()
        btn_import = QPushButton("ファイルを選択してインポート")
        btn_import.clicked.connect(self._import)
        btn_clear = QPushButton("クリア")
        btn_clear.clicked.connect(self._clear)
        btn_row.addWidget(btn_import)
        btn_row.addWidget(btn_clear)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self._table = QTableWidget(0, 7)
        self._table.setHorizontalHeaderLabels(
            ["会員番号", "col1", "col2", "col3", "col4", "col5", "マッピング列名"])
        self._table.horizontalHeader().setSectionResizeMode(
            6, QHeaderView.ResizeMode.Stretch)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self._table)

        self._status_label = QLabel("（未読み込み）")
        layout.addWidget(self._status_label)

        btn_close = QHBoxLayout()
        btn_ok = QPushButton("OK（このデータで送信）")
        btn_ok.clicked.connect(self.accept)
        btn_cancel = QPushButton("キャンセル（差し込みなし）")
        btn_cancel.clicked.connect(self.reject)
        btn_close.addWidget(btn_cancel)
        btn_close.addStretch()
        btn_close.addWidget(btn_ok)
        layout.addLayout(btn_close)

    def _import(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "差し込みデータを選択", "",
            "Excel/CSV (*.xlsx *.xls *.csv)")
        if not path:
            return
        try:
            headers, rows = load_member_file(path)
        except Exception as e:
            QMessageBox.critical(self, "エラー", str(e))
            return
        if not headers:
            QMessageBox.warning(self, "エラー", "ファイルが空です。")
            return

        # 列マッピングダイアログ
        from app.ui.dialogs._col_mapping_dialog import ColMappingDialog
        dlg = ColMappingDialog(headers, parent=self)
        if not dlg.exec():
            return
        mapping = dlg.get_mapping()  # {"member_number": idx, "col1": idx, ...}

        if "member_number" not in mapping:
            QMessageBox.warning(self, "エラー", "「会員番号」列のマッピングは必須です。")
            return

        self._merge_data = {}
        skipped = 0
        for row in rows:
            def cell(idx):
                if idx is None or idx >= len(row):
                    return ""
                v = row[idx]
                return str(v).strip() if v is not None else ""

            mn = cell(mapping.get("member_number"))
            if not mn:
                skipped += 1
                continue
            self._merge_data[mn] = {k: cell(mapping.get(k)) for k in _COL_KEYS}
            self._col_names = [headers[mapping[k]] if k in mapping else ""
                               for k in _COL_KEYS]

        self._refresh_table()
        self._status_label.setText(
            f"{len(self._merge_data)} 件読み込み済み。スキップ: {skipped} 件。")

    def _refresh_table(self):
        self._table.setRowCount(0)
        for mn, cols in self._merge_data.items():
            r = self._table.rowCount()
            self._table.insertRow(r)
            self._table.setItem(r, 0, QTableWidgetItem(mn))
            for i, k in enumerate(_COL_KEYS, 1):
                self._table.setItem(r, i, QTableWidgetItem(cols.get(k, "")))
            self._table.setItem(r, 6, QTableWidgetItem(
                " / ".join(n for n in self._col_names if n)))

    def _clear(self):
        self._merge_data = {}
        self._table.setRowCount(0)
        self._status_label.setText("（クリア済み）")

    def get_merge_data(self) -> dict[str, dict]:
        return self._merge_data
