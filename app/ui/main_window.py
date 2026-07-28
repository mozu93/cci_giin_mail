from PyQt6.QtWidgets import (
    QMainWindow, QTabWidget, QWidget, QVBoxLayout, QLabel, QApplication,
    QMessageBox,
)
from PyQt6.QtGui import QAction
from app.database.connection import get_session
from app.services.staff_service import get_staff_by_name
from app.ui.member_tab import MemberTab
from app.ui.meeting_tab import MeetingTab
from app.ui.send_tab import SendTab
from app.ui.template_tab import TemplateTab
from app.ui.settings_tab import SettingsTab
from app.ui.history_tab import HistoryTab


class MainWindow(QMainWindow):
    def __init__(self, staff_name: str = "", readonly: bool = False):
        super().__init__()
        self._staff_name = staff_name
        self._readonly = readonly
        session = get_session()
        try:
            staff = get_staff_by_name(session, staff_name) if staff_name else None
        finally:
            session.close()
        self._is_admin = bool(staff and staff.is_admin)
        if readonly:
            title = "商工会議所メール配信システム　【閲覧専用】"
        elif staff_name:
            title = f"商工会議所メール配信システム　［{staff_name}］"
        else:
            title = "商工会議所メール配信システム"
        self.setWindowTitle(title)
        self.resize(1280, 728)
        self.setMinimumSize(700, 500)
        self._setup_menu()
        self._build_tabs()
        self._setup_statusbar()
        self._center_on_screen()

    def _setup_menu(self):
        menubar = self.menuBar()
        help_menu = menubar.addMenu("ヘルプ")

        act_manual = QAction("使い方マニュアル", self)
        act_manual.triggered.connect(lambda: self._open_manual("user_manual.html"))
        help_menu.addAction(act_manual)

        if self._is_admin:
            act_admin_manual = QAction("管理者マニュアル", self)
            act_admin_manual.triggered.connect(
                lambda: self._open_manual("admin_manual.html"))
            help_menu.addAction(act_admin_manual)

        help_menu.addSeparator()
        act_check_update = QAction("更新を確認", self)
        act_check_update.triggered.connect(
            lambda: self._banner.check_now(manual=True))
        help_menu.addAction(act_check_update)

    def _open_manual(self, filename: str):
        import os
        import sys
        from pathlib import Path
        if getattr(sys, "frozen", False):
            base = Path(sys._MEIPASS)
        else:
            base = Path(__file__).parent.parent.parent
        manual = base / "docs" / "manual" / filename
        if manual.exists():
            os.startfile(str(manual))
        else:
            QMessageBox.warning(self, "マニュアル", f"マニュアルファイルが見つかりません:\n{manual}")

    def _center_on_screen(self):
        screen = QApplication.primaryScreen().availableGeometry()
        self.move(
            screen.center().x() - self.width() // 2,
            screen.center().y() - self.height() // 2,
        )

    def _build_tabs(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        from app.ui.update_banner import UpdateBanner
        self._banner = UpdateBanner(self)
        layout.addWidget(self._banner)

        tabs = QTabWidget()
        if self._readonly:
            tabs.addTab(
                MeetingTab(staff_name="", readonly=True), "出欠確認")
        else:
            member_tab = MemberTab()
            member_tab.set_staff_name(self._staff_name)
            tabs.addTab(member_tab, "名簿管理")
            tabs.addTab(MeetingTab(staff_name=self._staff_name), "会議管理")
            tabs.addTab(SendTab(staff_name=self._staff_name), "メール送信")
            tabs.addTab(TemplateTab(staff_name=self._staff_name), "テンプレート")
            tabs.addTab(SettingsTab(staff_name=self._staff_name), "設定")
            tabs.addTab(HistoryTab(), "送信履歴")
        tabs.currentChanged.connect(lambda idx: self._on_tab_change(tabs, idx))
        layout.addWidget(tabs)

    def _setup_statusbar(self):
        from app.version import __version__
        sb = self.statusBar()
        sb.setStyleSheet(
            "QStatusBar { background: #F8FAFC; border-top: 1px solid #E2E8F0; "
            "font-size: 12px; color: #64748B; }"
            "QStatusBar::item { border: none; }"
        )
        ver_lbl = QLabel(f"v{__version__}")
        ver_lbl.setStyleSheet("color: #94A3B8; font-size: 11px; padding: 0 8px;")
        sb.addPermanentWidget(ver_lbl)

    def closeEvent(self, event):
        self._export_html_silent()
        super().closeEvent(event)

    def _export_html_silent(self):
        from app.utils.app_config import get_html_export_path
        path = get_html_export_path()
        if not path:
            return
        try:
            from app.services.html_export_service import export_attendance_html
            export_attendance_html(path)
        except Exception:
            pass

    def _on_tab_change(self, tabs: QTabWidget, idx: int):
        widget = tabs.widget(idx)
        if hasattr(widget, "refresh"):
            widget.refresh()
