import sys
from PyQt6.QtWidgets import QApplication
from app.ui.main_window import MainWindow
from app.ui.dialogs.login_dialog import LoginDialog


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("cci-mail")

    dlg = LoginDialog()
    if dlg.exec() != LoginDialog.DialogCode.Accepted:
        sys.exit(0)

    window = MainWindow(staff_name=dlg.staff_name())
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
