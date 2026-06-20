from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel


class TemplateTab(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("テンプレート管理（実装予定）"))
