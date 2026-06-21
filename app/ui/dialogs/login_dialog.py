from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QPushButton, QMessageBox
)
from PyQt6.QtCore import Qt


class LoginDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("ログイン")
        self.setFixedSize(360, 160)
        self.setWindowFlags(
            Qt.WindowType.Dialog | Qt.WindowType.WindowTitleHint)

        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.addWidget(QLabel("担当者を選択してください"))

        self._combo = QComboBox()
        layout.addWidget(self._combo)

        btn_row = QHBoxLayout()
        btn_login = QPushButton("ログイン")
        btn_login.setDefault(True)
        btn_login.clicked.connect(self._login)
        btn_row.addStretch()
        btn_row.addWidget(btn_login)
        layout.addLayout(btn_row)

        self._staff_name = ""
        self._load_staff()

    def _load_staff(self):
        from app.database.connection import get_session
        from app.services.staff_service import get_all_staff
        session = get_session()
        try:
            staff = [s for s in get_all_staff(session) if s.is_active]
        finally:
            session.close()
        self._combo.clear()
        self._combo.addItem("（選択してください）", "")
        for s in staff:
            self._combo.addItem(s.name, s.name)

    def _login(self):
        name = self._combo.currentData()
        if not name:
            QMessageBox.warning(self, "未選択", "担当者を選択してください。")
            return
        self._staff_name = name
        self.accept()

    def staff_name(self) -> str:
        return self._staff_name
