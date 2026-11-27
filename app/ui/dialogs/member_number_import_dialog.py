from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QComboBox, QCheckBox,
    QRadioButton, QButtonGroup, QPushButton, QLabel, QPlainTextEdit,
)
from app.services.member_number_match_service import (
    MODE_MATCHED, MODE_UNMATCHED, extract_numbers, guess_has_header,
    match_member_numbers, resolve_target_ids,
)
from app.database.connection import get_session


def _column_label(index: int) -> str:
    """0 → A, 1 → B ... のExcel風の列名"""
    name = ""
    n = index
    while True:
        name = chr(ord("A") + n % 26) + name
        n = n // 26 - 1
        if n < 0:
            return name


class MemberNumberImportDialog(QDialog):
    """会員番号の一覧ファイルから、送信先としてチェックを入れる会員を決める。"""

    def __init__(self, rows: list[list], members: list, parent=None):
        super().__init__(parent)
        self.setWindowTitle("会員番号一覧から送信先を選ぶ")
        self.setMinimumWidth(460)
        self._rows = rows
        self._members = members
        self._target_ids: set[int] = set()
        self._match = None
        self._build()
        self._update_preview()

    def _build(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self._chk_header = QCheckBox("1行目は見出し行")
        # 1行目が会員番号そのものなら見出しではないので、既定でオフにする
        self._chk_header.setChecked(guess_has_header(self._rows, self._members))
        self._chk_header.toggled.connect(self._on_header_toggled)
        form.addRow("", self._chk_header)

        self._col_combo = QComboBox()
        self._col_combo.currentIndexChanged.connect(self._update_preview)
        form.addRow("会員番号の列", self._col_combo)
        layout.addLayout(form)
        self._fill_columns()

        self._rb_matched = QRadioButton("一覧に載っている会員にチェックを入れる")
        self._rb_unmatched = QRadioButton(
            "一覧に載っていない会員にチェックを入れる（一覧を除外リストとして使う）")
        self._rb_matched.setChecked(True)
        grp = QButtonGroup(self)
        grp.addButton(self._rb_matched)
        grp.addButton(self._rb_unmatched)
        self._rb_matched.toggled.connect(self._update_preview)
        layout.addWidget(self._rb_matched)
        layout.addWidget(self._rb_unmatched)

        self._summary = QLabel("")
        self._summary.setWordWrap(True)
        layout.addWidget(self._summary)
        self._detail = QPlainTextEdit()
        self._detail.setReadOnly(True)
        self._detail.setMaximumHeight(120)
        layout.addWidget(self._detail)

        btn_row = QHBoxLayout()
        btn_cancel = QPushButton("キャンセル")
        btn_cancel.clicked.connect(self.reject)
        self._btn_ok = QPushButton("チェックを入れる")
        self._btn_ok.setDefault(True)
        self._btn_ok.clicked.connect(self.accept)
        btn_row.addWidget(btn_cancel)
        btn_row.addStretch()
        btn_row.addWidget(self._btn_ok)
        layout.addLayout(btn_row)

    def _fill_columns(self):
        has_header = self._chk_header.isChecked()
        width = max((len(r) for r in self._rows), default=0)
        self._col_combo.blockSignals(True)
        self._col_combo.clear()
        selected = 0
        for i in range(width):
            label = f"{_column_label(i)}列"
            if (has_header and self._rows and i < len(self._rows[0])
                    and self._rows[0][i] not in (None, "")):
                label += f"（{self._rows[0][i]}）"
                if "会員番号" in str(self._rows[0][i]) and selected == 0:
                    selected = i
            self._col_combo.addItem(label, i)
        self._col_combo.setCurrentIndex(selected)
        self._col_combo.blockSignals(False)

    def _on_header_toggled(self):
        current = self._col_combo.currentData()
        self._fill_columns()
        if current is not None:
            idx = self._col_combo.findData(current)
            if idx >= 0:
                self._col_combo.setCurrentIndex(idx)
        self._update_preview()

    def _update_preview(self):
        column = self._col_combo.currentData()
        if column is None:
            self._target_ids = set()
            self._summary.setText("会員番号の列がありません。")
            self._detail.clear()
            self._btn_ok.setEnabled(False)
            return
        numbers = extract_numbers(
            self._rows, column, self._chk_header.isChecked())
        session = get_session()
        try:
            self._match = match_member_numbers(session, numbers, self._members)
        finally:
            session.close()
        self._target_ids = resolve_target_ids(
            self._members, self._match, self.mode)
        m = self._match
        lines = [
            f"一覧の会員番号: {m.total}件"
            + (f"（重複 {m.duplicates}件は1件として扱います）" if m.duplicates else ""),
            f"名簿と一致: {len(m.matched_ids)}件 ／ 一致なし: "
            f"{len(m.not_found) + len(m.inactive)}件",
            f"→ チェックを入れる会員: {len(self._target_ids)}件",
        ]
        self._summary.setText("\n".join(lines))
        detail = []
        if m.not_found:
            detail.append("【名簿に無い会員番号】\n" + "、".join(m.not_found))
        if m.inactive:
            detail.append("【退任済みの会員番号】\n" + "、".join(m.inactive))
        self._detail.setPlainText("\n\n".join(detail))
        self._btn_ok.setEnabled(bool(self._target_ids))

    @property
    def mode(self) -> str:
        return MODE_MATCHED if self._rb_matched.isChecked() else MODE_UNMATCHED

    def get_target_ids(self) -> set[int]:
        return set(self._target_ids)
