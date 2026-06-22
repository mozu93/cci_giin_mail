from PyQt6.QtWidgets import QMainWindow, QTabWidget
from app.ui.member_tab import MemberTab
from app.ui.meeting_tab import MeetingTab
from app.ui.send_tab import SendTab
from app.ui.template_tab import TemplateTab
from app.ui.settings_tab import SettingsTab
from app.ui.history_tab import HistoryTab


class MainWindow(QMainWindow):
    def __init__(self, staff_name: str = ""):
        super().__init__()
        self._staff_name = staff_name
        self.setWindowTitle(
            f"商工会議所メール配信システム　［{staff_name}］" if staff_name
            else "商工会議所メール配信システム"
        )
        self.resize(780, 728)
        self.setMinimumSize(700, 500)
        self._build_tabs()
        self._center_on_screen()

    def _center_on_screen(self):
        from PyQt6.QtWidgets import QApplication
        screen = QApplication.primaryScreen().availableGeometry()
        self.move(
            screen.center().x() - self.width() // 2,
            screen.center().y() - self.height() // 2,
        )

    def _build_tabs(self):
        tabs = QTabWidget()
        self.setCentralWidget(tabs)
        member_tab = MemberTab()
        member_tab.set_staff_name(self._staff_name)
        tabs.addTab(member_tab, "名簿管理")
        tabs.addTab(MeetingTab(staff_name=self._staff_name), "会議管理")
        tabs.addTab(SendTab(staff_name=self._staff_name), "メール送信")
        tabs.addTab(TemplateTab(), "テンプレート")
        tabs.addTab(SettingsTab(), "設定")
        tabs.addTab(HistoryTab(), "送信履歴")
        tabs.currentChanged.connect(lambda idx: self._on_tab_change(tabs, idx))

    def _on_tab_change(self, tabs: QTabWidget, idx: int):
        widget = tabs.widget(idx)
        if hasattr(widget, "refresh"):
            widget.refresh()
