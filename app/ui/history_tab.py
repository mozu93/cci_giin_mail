from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel


class HistoryTab(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("送信履歴（実装予定）"))
