import os

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QPlainTextEdit, QPushButton, QHBoxLayout,
)


def format_recipient_details(targets: list[dict]) -> str:
    """送信直前確認用に、全企業の実宛先を読みやすく整形する。"""
    blocks = []
    for target in targets:
        to_address = target.get("to_address") or "（なし・送信時スキップ）"
        cc_addresses = ", ".join(target.get("cc_addresses", [])) or "なし"
        bcc_addresses = ", ".join(target.get("bcc_addresses", [])) or "なし"
        blocks.append(
            f"【{target.get('org_name', '')}】\n"
            f"To: {to_address}\n"
            f"CC: {cc_addresses}\n"
            f"BCC: {bcc_addresses}\n"
            "添付: "
            + (", ".join(
                os.path.basename(path)
                for path in target.get("attachments", [])) or "なし")
        )
        if "original_to_address" in target:
            original_cc = ", ".join(
                target.get("original_cc_addresses", [])) or "なし"
            original_bcc = ", ".join(
                target.get("original_bcc_addresses", [])) or "なし"
            blocks[-1] += (
                "\n--- テストモードで振替前の宛先 ---\n"
                f"本来のTo: {target.get('original_to_address') or 'なし'}\n"
                f"本来のCC: {original_cc}\n"
                f"本来のBCC: {original_bcc}"
            )
    return "\n\n".join(blocks)


class SendConfirmDialog(QDialog):
    """全送信先を表示してから送信を確定するダイアログ。"""

    def __init__(self, summary: str, targets: list[dict], parent=None):
        super().__init__(parent)
        self.setWindowTitle("送信確認")
        self.resize(720, 640)

        layout = QVBoxLayout(self)
        summary_label = QLabel(summary)
        summary_label.setWordWrap(True)
        layout.addWidget(summary_label)

        layout.addWidget(QLabel("<b>全送信先（To／CC／BCC）</b>"))
        details = QPlainTextEdit()
        details.setReadOnly(True)
        details.setPlainText(format_recipient_details(targets))
        layout.addWidget(details, 1)

        warning = QLabel("送信後は取り消せません。宛先を確認してください。")
        warning.setStyleSheet("color: #DC2626; font-weight: bold;")
        layout.addWidget(warning)

        buttons = QHBoxLayout()
        buttons.addStretch()
        btn_send = QPushButton("送信する")
        btn_send.clicked.connect(self.accept)
        btn_cancel = QPushButton("キャンセル")
        btn_cancel.clicked.connect(self.reject)
        btn_cancel.setDefault(True)
        buttons.addWidget(btn_send)
        buttons.addWidget(btn_cancel)
        layout.addLayout(buttons)
