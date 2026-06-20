from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel


class MemberTab(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("名簿管理（実装予定）"))
