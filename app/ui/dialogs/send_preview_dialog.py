# app/ui/dialogs/send_preview_dialog.py
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QLabel, QLineEdit, QPlainTextEdit, QPushButton, QSplitter, QWidget,
    QFormLayout
)
from PyQt6.QtCore import Qt


class SendPreviewDialog(QDialog):
    def __init__(self, targets: list[dict], parent=None):
        super().__init__(parent)
        self._targets = targets
        self.setWindowTitle("差し込みプレビュー")
        self.resize(760, 560)
        self._build()
        if targets:
            self._recipient_list.setCurrentRow(0)

    def _build(self):
        layout = QVBoxLayout(self)

        label = QLabel(
            f"宛先 {len(self._targets)} 件の差し込み後の内容を確認できます。"
            "　左の一覧から宛先を選択してください。"
        )
        layout.addWidget(label)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # 左：宛先リスト
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addWidget(QLabel("<b>宛先一覧</b>"))
        self._recipient_list = QListWidget()
        for t in self._targets:
            item = QListWidgetItem(f"{t['org_name']}　{t['name']}")
            self._recipient_list.addItem(item)
        self._recipient_list.currentRowChanged.connect(self._on_select)
        left_layout.addWidget(self._recipient_list)
        left.setMinimumWidth(200)
        splitter.addWidget(left)

        # 右：差し込み後プレビュー
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.addWidget(QLabel("<b>差し込み後プレビュー</b>"))

        form = QFormLayout()
        self._to_label = QLineEdit()
        self._to_label.setReadOnly(True)
        self._subject_edit = QLineEdit()
        self._subject_edit.setReadOnly(True)
        form.addRow("宛先", self._to_label)
        form.addRow("件名", self._subject_edit)
        right_layout.addLayout(form)

        self._body_edit = QPlainTextEdit()
        self._body_edit.setReadOnly(True)
        right_layout.addWidget(self._body_edit)

        splitter.addWidget(right)
        splitter.setSizes([210, 540])
        layout.addWidget(splitter)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_close = QPushButton("閉じる")
        btn_close.clicked.connect(self.accept)
        btn_row.addWidget(btn_close)
        layout.addLayout(btn_row)

    def _on_select(self, row: int):
        if row < 0 or row >= len(self._targets):
            return
        t = self._targets[row]
        addr = t.get("to_address") or "（メールアドレス無し）"
        self._to_label.setText(f"{t['org_name']}　{t['name']}　＜{addr}＞")
        self._subject_edit.setText(t.get("subject", ""))
        self._body_edit.setPlainText(t.get("body", ""))
