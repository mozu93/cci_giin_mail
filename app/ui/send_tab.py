from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel


class SendTab(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("メール送信（実装予定）"))
