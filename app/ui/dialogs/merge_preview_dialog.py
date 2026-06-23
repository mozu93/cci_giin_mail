# app/ui/dialogs/merge_preview_dialog.py
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QPushButton, QLabel, QFileDialog, QMessageBox,
    QGroupBox, QFormLayout, QLineEdit, QPlainTextEdit, QComboBox,
    QSplitter, QWidget
)
from PyQt6.QtCore import Qt
from app.services.import_service import load_member_file
from app.services.email_service import render_body

_COL_KEYS = ["col1", "col2", "col3", "col4", "col5"]


class MergePreviewDialog(QDialog):
    def __init__(self, parent=None, subject: str = "", body: str = ""):
        super().__init__(parent)
        self.setWindowTitle("差し込みデータ設定")
        self.resize(720, 560)
        self._merge_data: dict[str, dict] = {}
        self._col_names: list[str] = []
        self._col_labels: dict[str, str] = {}
        self._tmpl_subject = subject
        self._tmpl_body = body
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            "差し込みデータCSV/ExcelをインポートしてCol1〜Col5に対応させます。\n"
            "「会員番号」列が必須です（名簿との突合キー）。\n"
            "ラベルを入力すると {ラベル名} としてテンプレートで使えます（例: {参加費}）。"
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

        splitter = QSplitter(Qt.Orientation.Vertical)

        # 上：データ一覧テーブル
        self._table = QTableWidget(0, 7)
        self._table.setHorizontalHeaderLabels(
            ["会員番号", "差し込み1", "差し込み2", "差し込み3", "差し込み4", "差し込み5",
             "マッピング列名"])
        self._table.horizontalHeader().setSectionResizeMode(
            6, QHeaderView.ResizeMode.Stretch)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        splitter.addWidget(self._table)

        # 下：差し込みプレビューパネル
        preview_grp = QGroupBox("差し込みプレビュー")
        preview_layout = QVBoxLayout(preview_grp)

        row_sel_row = QHBoxLayout()
        row_sel_row.addWidget(QLabel("行を選択:"))
        self._preview_combo = QComboBox()
        self._preview_combo.setMinimumWidth(240)
        self._preview_combo.currentIndexChanged.connect(self._update_preview)
        row_sel_row.addWidget(self._preview_combo)
        row_sel_row.addStretch()
        note = QLabel("※ 事業所名・氏名は実際の送信時に差し込まれます")
        note.setStyleSheet("color: #6B7280; font-size: 11px;")
        row_sel_row.addWidget(note)
        preview_layout.addLayout(row_sel_row)

        pform = QFormLayout()
        self._prev_subject = QLineEdit()
        self._prev_subject.setReadOnly(True)
        pform.addRow("件名", self._prev_subject)
        preview_layout.addLayout(pform)

        self._prev_body = QPlainTextEdit()
        self._prev_body.setReadOnly(True)
        self._prev_body.setMaximumHeight(120)
        preview_layout.addWidget(self._prev_body)

        splitter.addWidget(preview_grp)
        splitter.setSizes([300, 220])
        layout.addWidget(splitter)

        self._status_label = QLabel("（未読み込み）")
        layout.addWidget(self._status_label)

        btn_close = QHBoxLayout()
        btn_ok = QPushButton("登録（差し込みデータを確定）")
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

        from app.ui.dialogs._col_mapping_dialog import ColMappingDialog
        dlg = ColMappingDialog(headers, parent=self)
        if not dlg.exec():
            return
        mapping = dlg.get_mapping()
        self._col_labels = dlg.get_labels()

        if "member_number" not in mapping:
            QMessageBox.warning(self, "エラー", "「会員番号」列のマッピングは必須です。")
            return

        self._merge_data = {}
        self._col_names = []
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
        self._refresh_preview_combo()
        self._status_label.setText(
            f"{len(self._merge_data)} 件読み込み済み。スキップ: {skipped} 件。")

    def _col_header(self, i: int) -> str:
        key = _COL_KEYS[i]
        label = self._col_labels.get(key, "")
        base = f"差し込み{i + 1}"
        return f"{base}（{label}）" if label else base

    def _refresh_table(self):
        headers = ["会員番号"]
        for i in range(5):
            headers.append(self._col_header(i))
        headers.append("マッピング列名")
        self._table.setHorizontalHeaderLabels(headers)

        self._table.setRowCount(0)
        for mn, cols in self._merge_data.items():
            r = self._table.rowCount()
            self._table.insertRow(r)
            self._table.setItem(r, 0, QTableWidgetItem(mn))
            for i, k in enumerate(_COL_KEYS, 1):
                self._table.setItem(r, i, QTableWidgetItem(cols.get(k, "")))
            self._table.setItem(r, 6, QTableWidgetItem(
                " / ".join(n for n in self._col_names if n)))

    def _refresh_preview_combo(self):
        self._preview_combo.blockSignals(True)
        self._preview_combo.clear()
        for mn in self._merge_data:
            self._preview_combo.addItem(f"会員番号: {mn}", mn)
        self._preview_combo.blockSignals(False)
        self._update_preview()

    def _update_preview(self):
        if not self._tmpl_subject and not self._tmpl_body:
            self._prev_subject.setText("（テンプレート未選択）")
            self._prev_body.setPlainText("テンプレートを選択してから差し込みデータを設定すると\nここにプレビューが表示されます。")
            return
        mn = self._preview_combo.currentData()
        if not mn or mn not in self._merge_data:
            self._prev_subject.clear()
            self._prev_body.clear()
            return
        merge = self._merge_data[mn]
        context = {
            "事業所名": "（事業所名）", "役職名": "（役職名）",
            "氏名": "（氏名）", "会議所役職名": "（会議所役職名）",
            **{k: merge.get(k, "") for k in _COL_KEYS},
        }
        # ラベルエイリアスを追加
        for col_key, label in self._col_labels.items():
            context[label] = context.get(col_key, "")

        self._prev_subject.setText(render_body(self._tmpl_subject, context))
        self._prev_body.setPlainText(render_body(self._tmpl_body, context))

    def _clear(self):
        self._merge_data = {}
        self._col_labels = {}
        self._col_names = []
        self._table.setRowCount(0)
        self._preview_combo.clear()
        self._prev_subject.clear()
        self._prev_body.clear()
        self._status_label.setText("（クリア済み）")

    def get_merge_data(self) -> dict[str, dict]:
        return self._merge_data

    def get_col_labels(self) -> dict[str, str]:
        return self._col_labels
