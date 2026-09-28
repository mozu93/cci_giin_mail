from PyQt6.QtWidgets import QLabel
from PyQt6.QtCore import QTimer
from app.ui.theme import style


def show_inline_message(label: QLabel, text: str, ms: int = 2500) -> None:
    label.setText(text)
    style(label, "color: ${success};")
    # ラベルの子にしたタイマーは、画面を閉じてラベルが消えると一緒に破棄される。
    timer = label.findChild(QTimer, "_inline_message_timer")
    if timer is None:
        timer = QTimer(label)
        timer.setObjectName("_inline_message_timer")
        timer.setSingleShot(True)
        timer.timeout.connect(label.clear)
    timer.start(ms)
