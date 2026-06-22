from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QPushButton, QMessageBox, QInputDialog
)
from PyQt6.QtCore import Qt


class LoginDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("ログイン")
        self.setFixedSize(360, 200)
        self.setWindowFlags(
            Qt.WindowType.Dialog | Qt.WindowType.WindowTitleHint)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        self._label = QLabel("担当者を選択してください")
        layout.addWidget(self._label)

        self._combo = QComboBox()
        layout.addWidget(self._combo)

        self._hint = QLabel(
            "担当者が登録されていません。\n「職員を追加」ボタンで最初の職員を登録してください。"
        )
        self._hint.setWordWrap(True)
        self._hint.setStyleSheet("color: #c0392b;")
        layout.addWidget(self._hint)

        btn_row = QHBoxLayout()
        self._btn_add = QPushButton("職員を追加")
        self._btn_add.clicked.connect(self._add_staff)
        btn_login = QPushButton("ログイン")
        btn_login.setDefault(True)
        btn_login.clicked.connect(self._login)
        btn_row.addWidget(self._btn_add)
        btn_row.addStretch()
        btn_row.addWidget(btn_login)
        layout.addLayout(btn_row)

        self._staff_name = ""
        self._load_staff()
        self._center_on_screen()

    def _center_on_screen(self):
        from PyQt6.QtWidgets import QApplication
        screen = QApplication.primaryScreen().availableGeometry()
        self.move(
            screen.center().x() - self.width() // 2,
            screen.center().y() - self.height() // 2,
        )

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

        no_staff = len(staff) == 0
        self._hint.setVisible(no_staff)
        self._btn_add.setVisible(no_staff)

    def _add_staff(self):
        name, ok = QInputDialog.getText(self, "職員を追加", "職員名を入力してください：")
        if not ok or not name.strip():
            return
        from app.database.connection import get_session
        from app.services.staff_service import create_staff
        session = get_session()
        try:
            create_staff(session, name.strip())
        finally:
            session.close()
        self._load_staff()
        QMessageBox.information(self, "登録完了", f"「{name.strip()}」を登録しました。")

    def _login(self):
        name = self._combo.currentData()
        if not name:
            QMessageBox.warning(self, "未選択", "担当者を選択してください。")
            return
        self._staff_name = name
        self.accept()

    def staff_name(self) -> str:
        return self._staff_name
