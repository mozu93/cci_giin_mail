# app/ui/dialogs/_col_mapping_dialog.py
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QComboBox, QPushButton,
    QHBoxLayout, QLabel
)

_FIELD_LABELS = [
    ("member_number", "会員番号 *"),
    ("col1", "col1"),
    ("col2", "col2"),
    ("col3", "col3"),
    ("col4", "col4"),
    ("col5", "col5"),
]


class ColMappingDialog(QDialog):
    def __init__(self, headers: list[str], parent=None):
        super().__init__(parent)
        self.setWindowTitle("列マッピング")
        self._headers = headers
        self._combos: dict[str, QComboBox] = {}
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("各フィールドに対応するファイルの列を選択してください。"))
        form = QFormLayout()
        for field_key, label in _FIELD_LABELS:
            combo = QComboBox()
            combo.addItem("（使用しない）", None)
            for i, h in enumerate(self._headers):
                combo.addItem(h, i)
            # 自動マッピング
            lower_h = [h.lower() for h in self._headers]
            auto_keys = {"member_number": ["会員番号", "membernumber", "member_number"]}
            for k in auto_keys.get(field_key, []):
                if k in lower_h:
                    combo.setCurrentIndex(lower_h.index(k) + 1)
                    break
            self._combos[field_key] = combo
            form.addRow(label, combo)
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
