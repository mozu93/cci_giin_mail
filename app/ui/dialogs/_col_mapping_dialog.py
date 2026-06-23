# app/ui/dialogs/_col_mapping_dialog.py
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QComboBox, QPushButton,
    QHBoxLayout, QLabel, QLineEdit, QWidget
)

_FIELD_LABELS = [
    ("member_number", "会員番号 *", False),
    ("col1", "差し込み1", True),
    ("col2", "差し込み2", True),
    ("col3", "差し込み3", True),
    ("col4", "差し込み4", True),
    ("col5", "差し込み5", True),
]


class ColMappingDialog(QDialog):
    def __init__(self, headers: list[str], parent=None):
        super().__init__(parent)
        self.setWindowTitle("列マッピング")
        self._headers = headers
        self._combos: dict[str, QComboBox] = {}
        self._label_edits: dict[str, QLineEdit] = {}
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            "各フィールドに対応するファイルの列を選択してください。\n"
            "「ラベル」を入力すると、テンプレートで {ラベル名} として使えます。"
        ))

        form = QFormLayout()
        lower_h = [h.lower() for h in self._headers]
        auto_keys = {"member_number": ["会員番号", "membernumber", "member_number"]}

        for field_key, row_label, has_label in _FIELD_LABELS:
            combo = QComboBox()
            combo.addItem("（使用しない）", None)
            for i, h in enumerate(self._headers):
                combo.addItem(h, i)

            for k in auto_keys.get(field_key, []):
                if k in lower_h:
                    combo.setCurrentIndex(lower_h.index(k) + 1)
                    break

            self._combos[field_key] = combo

            if has_label:
                row_w = QWidget()
                row_l = QHBoxLayout(row_w)
                row_l.setContentsMargins(0, 0, 0, 0)
                row_l.addWidget(combo, 3)
                lbl_edit = QLineEdit()
                lbl_edit.setPlaceholderText("ラベル（例：参加費）")
                row_l.addWidget(lbl_edit, 2)
                self._label_edits[field_key] = lbl_edit
                form.addRow(row_label, row_w)
            else:
                form.addRow(row_label, combo)

        layout.addLayout(form)

        btn_row = QHBoxLayout()
        btn_cancel = QPushButton("キャンセル")
        btn_cancel.clicked.connect(self.reject)
        btn_ok = QPushButton("OK")
        btn_ok.clicked.connect(self.accept)
        btn_row.addWidget(btn_cancel)
        btn_row.addStretch()
        btn_row.addWidget(btn_ok)
        layout.addLayout(btn_row)

    def get_mapping(self) -> dict[str, int]:
        result = {}
        for field_key, combo in self._combos.items():
            idx = combo.currentData()
            if idx is not None:
                result[field_key] = idx
        return result

    def get_labels(self) -> dict[str, str]:
        return {k: v.text().strip()
                for k, v in self._label_edits.items()
                if v.text().strip()}
