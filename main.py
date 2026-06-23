import sys
from PyQt6.QtWidgets import QApplication
from app.ui.main_window import MainWindow
from app.ui.dialogs.login_dialog import LoginDialog


_GLOBAL_STYLE = """
QPushButton {
    background-color: #F0F4F8;
    border: 1px solid #94A3B8;
    border-radius: 4px;
    padding: 4px 10px;
    color: #1E293B;
    min-height: 26px;
}
QPushButton:hover {
    background-color: #DBEAFE;
    border-color: #3B82F6;
    color: #1D4ED8;
}
QPushButton:pressed {
    background-color: #BFDBFE;
    border-color: #2563EB;
}
QPushButton:disabled {
    background-color: #F1F5F9;
    border-color: #CBD5E1;
    color: #94A3B8;
}
QLineEdit, QTextEdit, QComboBox {
    border: 1px solid #CBD5E1;
    border-radius: 3px;
    padding: 3px 6px;
    background-color: #FFFFFF;
    selection-background-color: #BFDBFE;
}
QLineEdit:focus, QTextEdit:focus {
    border-color: #3B82F6;
}
QGroupBox {
    font-weight: bold;
    border: 1px solid #CBD5E1;
    border-radius: 4px;
    margin-top: 6px;
    padding-top: 4px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 8px;
    padding: 0 4px;
}
"""


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("cci-mail")
    app.setStyleSheet(_GLOBAL_STYLE)

    dlg = LoginDialog()
    if dlg.exec() != LoginDialog.DialogCode.Accepted:
        sys.exit(0)

    window = MainWindow(staff_name=dlg.staff_name(), readonly=dlg.readonly())
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
