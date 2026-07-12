# app/ui/dialogs/import_dialog.py
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QComboBox, QFileDialog, QMessageBox, QGroupBox, QFormLayout
)
from sqlalchemy.orm import Session
from app.services.import_service import load_member_file, import_members

_MEMBER_FIELDS = [
    ("member_number",    "会員番号 *"),
    ("organization_name","事業所名 *"),
    ("organization_kana","事業所名フリガナ"),
    ("title",            "役職名"),
    ("name",             "氏名 *"),
    ("name_kana",        "氏名フリガナ"),
    ("position_name",    "会議所役職"),
    ("committee_name",   "委員会"),
    ("email_1_address",  "メール1 アドレス"),
    ("email_1_label",    "メール1 ラベル"),
    ("email_2_address",  "メール2 アドレス"),
    ("email_2_label",    "メール2 ラベル"),
    ("email_3_address",  "メール3 アドレス"),
    ("email_3_label",    "メール3 ラベル"),
    ("email_4_address",  "メール4 アドレス"),
    ("email_4_label",    "メール4 ラベル"),
    ("email_5_address",  "メール5 アドレス"),
    ("email_5_label",    "メール5 ラベル"),
]


class ImportDialog(QDialog):
    def __init__(self, session: Session, staff_name: str = "", parent=None):
        super().__init__(parent)
        self._session = session
        self._staff_name = staff_name
        self._headers: list[str] = []
        self._rows: list[list] = []
        self.setWindowTitle("会員名簿インポート")
        self.setMinimumWidth(600)
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)

        # ファイル選択
        file_row = QHBoxLayout()
        self._file_path = QLineEdit()
        self._file_path.setReadOnly(True)
        btn_browse = QPushButton("ファイル選択")
        btn_browse.clicked.connect(self._browse)
        file_row.addWidget(QLabel("ファイル:"))
        file_row.addWidget(self._file_path, 1)
        file_row.addWidget(btn_browse)
        layout.addLayout(file_row)

        # データプレビュー（先頭5行）
        preview_grp = QGroupBox("データプレビュー（先頭5行）")
        preview_layout = QVBoxLayout(preview_grp)
        self._preview_table = QTableWidget(0, 0)
        self._preview_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._preview_table.setMaximumHeight(160)
        preview_layout.addWidget(self._preview_table)
        self._row_count_label = QLabel("")
        preview_layout.addWidget(self._row_count_label)
        layout.addWidget(preview_grp)

        # 列マッピング
        grp = QGroupBox("列マッピング（ファイル読み込み後に設定）")
        form = QFormLayout(grp)
        self._combos: dict[str, QComboBox] = {}
        for field_key, field_label in _MEMBER_FIELDS:
            combo = QComboBox()
            combo.addItem("（使用しない）", None)
            self._combos[field_key] = combo
            form.addRow(field_label, combo)
        layout.addWidget(grp)

        # ボタン
        btn_row = QHBoxLayout()
        btn_cancel = QPushButton("キャンセル")
        btn_cancel.clicked.connect(self.reject)
        self._btn_import = QPushButton("インポート実行")
        self._btn_import.setEnabled(False)
        self._btn_import.clicked.connect(self._run_import)
        btn_row.addWidget(btn_cancel)
        btn_row.addStretch()
        btn_row.addWidget(self._btn_import)
        layout.addLayout(btn_row)

    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "ファイルを選択", "",
            "Excel/CSV (*.xlsx *.xls *.csv)")
        if not path:
            return
        try:
            headers, rows = load_member_file(path)
        except Exception as e:
            QMessageBox.critical(self, "エラー", str(e))
            return
        self._on_file_loaded(path, headers, rows)

    def _on_file_loaded(self, path: str, headers: list[str], rows: list[list]):
        self._file_path.setText(path)
        self._headers = headers
        self._rows = rows
        self._populate_combos(headers)
        self._populate_preview(headers, rows)
        self._btn_import.setEnabled(True)

    def _populate_preview(self, headers: list[str], rows: list[list]):
        self._preview_table.setColumnCount(len(headers))
        self._preview_table.setHorizontalHeaderLabels(headers)
        preview_rows = rows[:5]
        self._preview_table.setRowCount(len(preview_rows))
        for r, row in enumerate(preview_rows):
            for c, value in enumerate(row):
                self._preview_table.setItem(r, c, QTableWidgetItem(str(value)))
        self._preview_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch)
        self._row_count_label.setText(f"全 {len(rows)} 件中 先頭{len(preview_rows)}件を表示")

    def _populate_combos(self, headers: list[str]):
        for combo in self._combos.values():
            combo.clear()
            combo.addItem("（使用しない）", None)
            for i, h in enumerate(headers):
                combo.addItem(h, i)
        # ヘッダー名で自動マッピング
        auto_map = {
            "会員番号": "member_number",
            "会員No": "member_number",
            "会員NO": "member_number",
            "会員ＮＯ": "member_number",
            "事業所名": "organization_name",
            "会社名": "organization_name",
            "法人名": "organization_name",
            "事業所名フリガナ": "organization_kana",
            "事業所名かな": "organization_kana",
            "役職名": "title",
            "役職": "title",
            "氏名": "name",
            "氏名フリガナ": "name_kana",
            "氏名かな": "name_kana",
            "会議所役職": "position_name",
            "会議所役職名": "position_name",
            "委員会": "committee_name",
            "所属委員会": "committee_name",
            "メール1アドレス": "email_1_address",
            "メール1ラベル": "email_1_label",
            "メール2アドレス": "email_2_address",
            "メール2ラベル": "email_2_label",
            "メール3アドレス": "email_3_address",
            "メール3ラベル": "email_3_label",
            "メール4アドレス": "email_4_address",
            "メール4ラベル": "email_4_label",
            "メール5アドレス": "email_5_address",
            "メール5ラベル": "email_5_label",
        }
        for i, h in enumerate(headers):
            if h in auto_map:
                field_key = auto_map[h]
                if field_key in self._combos:
                    self._combos[field_key].setCurrentIndex(i + 1)

    def _run_import(self):
        column_map = {}
        for field_key, combo in self._combos.items():
            idx = combo.currentData()
            if idx is not None:
                column_map[field_key] = idx
        if "member_number" not in column_map:
            QMessageBox.warning(self, "エラー", "「会員番号」列のマッピングは必須です。")
            return
        result = import_members(self._session, self._rows, column_map,
                                changed_by=self._staff_name or "インポート")
        msg = (f"インポート完了\n\n"
               f"新規登録: {result['created']} 件\n"
               f"更新: {result['updated']} 件\n")
        if result["errors"]:
            msg += f"\nエラー ({len(result['errors'])} 件):\n"
            msg += "\n".join(result["errors"][:10])
            if len(result["errors"]) > 10:
                msg += f"\n... 他 {len(result['errors']) - 10} 件"
        QMessageBox.information(self, "完了", msg)
        self.accept()
