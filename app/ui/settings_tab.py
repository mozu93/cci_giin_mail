from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel


class SettingsTab(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("設定（実装予定）"))
