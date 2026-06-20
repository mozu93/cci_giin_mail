from PyQt6.QtWidgets import QMainWindow, QTabWidget
from app.ui.member_tab import MemberTab
from app.ui.send_tab import SendTab
from app.ui.template_tab import TemplateTab
from app.ui.settings_tab import SettingsTab
from app.ui.history_tab import HistoryTab


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("商工会議所メール配信システム")
        self.resize(780, 728)
        self.setMinimumSize(700, 500)
        self._build_tabs()

    def _build_tabs(self):
        tabs = QTabWidget()
        self.setCentralWidget(tabs)
        tabs.addTab(MemberTab(), "名簿管理")
        tabs.addTab(SendTab(), "メール送信")
        tabs.addTab(TemplateTab(), "テンプレート")
        tabs.addTab(SettingsTab(), "設定")
        tabs.addTab(HistoryTab(), "送信履歴")
