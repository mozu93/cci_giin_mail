from PyQt6.QtWidgets import QLabel
from PyQt6.QtCore import QTimer


def show_inline_message(label: QLabel, text: str, ms: int = 2500) -> None:
    label.setText(text)
    label.setStyleSheet("color: #16A34A;")
    QTimer.singleShot(ms, lambda: label.setText(""))
