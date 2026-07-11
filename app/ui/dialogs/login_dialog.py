from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QPushButton, QMessageBox, QInputDialog, QFrame
)
from PyQt6.QtCore import Qt
from app.database.connection import get_session
from app.services.staff_service import get_all_staff, create_staff
from app.services.settings_service import get_last_staff, set_last_staff


class LoginDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("ログイン")
        self.setFixedSize(360, 260)
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
        self._btn_login = QPushButton("ログイン")
        self._btn_login.setDefault(True)
        self._btn_login.setEnabled(False)
        self._btn_login.clicked.connect(self._login)
        self._combo.currentIndexChanged.connect(
            lambda: self._btn_login.setEnabled(bool(self._combo.currentData())))
        btn_row.addWidget(self._btn_add)
        btn_row.addStretch()
        btn_row.addWidget(self._btn_login)
        layout.addLayout(btn_row)

        # 区切り線
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("color: #CBD5E1;")
        layout.addWidget(line)

        # 閲覧専用ボタン
        readonly_lbl = QLabel("出欠確認のみ行う場合（編集不可）")
        readonly_lbl.setStyleSheet("color: #64748B; font-size: 11px;")
        layout.addWidget(readonly_lbl)
        btn_readonly = QPushButton("閲覧専用でログイン")
        btn_readonly.setStyleSheet(
            "QPushButton { background-color: #F1F5F9; color: #475569; "
            "border: 1px solid #94A3B8; }"
            "QPushButton:hover { background-color: #E2E8F0; }"
        )
        btn_readonly.clicked.connect(self._login_readonly)
        layout.addWidget(btn_readonly)

        self._staff_name = ""
        self._readonly = False
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
        session = get_session()
        try:
            staff = [s for s in get_all_staff(session) if s.is_active]
        finally:
            session.close()
        self._combo.clear()
        self._combo.addItem("（選択してください）", "")
        last_staff = get_last_staff()
        last_index = 0
        for s in staff:
            self._combo.addItem(s.name, s.name)
            if s.name == last_staff:
                last_index = self._combo.count() - 1
        self._combo.setCurrentIndex(last_index)

        no_staff = len(staff) == 0
        self._hint.setVisible(no_staff)
        self._btn_add.setVisible(no_staff)
        self._btn_login.setEnabled(bool(self._combo.currentData()))

    def _add_staff(self):
        name, ok = QInputDialog.getText(self, "職員を追加", "職員名を入力してください：")
        if not ok or not name.strip():
            return
        session = get_session()
        try:
            create_staff(session, name.strip(), is_admin=True)
        finally:
            session.close()
        self._load_staff()
        QMessageBox.information(
            self, "登録完了",
            f"「{name.strip()}」を管理者として登録しました。")

    def _login(self):
        name = self._combo.currentData()
        if not name:
            QMessageBox.warning(self, "未選択", "担当者を選択してください。")
            return
        self._staff_name = name
        self._readonly = False
        set_last_staff(name)
        self.accept()

    def _login_readonly(self):
        self._staff_name = ""
        self._readonly = True
        self.accept()

    def staff_name(self) -> str:
        return self._staff_name

    def readonly(self) -> bool:
        return self._readonly
