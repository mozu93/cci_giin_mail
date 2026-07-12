import sys
import os
from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtGui import QIcon, QFont
from app.ui.main_window import MainWindow
from app.ui.dialogs.login_dialog import LoginDialog
from app.ui.dialogs.first_run_wizard import FirstRunWizard


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
    _font = app.font()
    _font.setPointSizeF(10.5)
    app.setFont(_font)
    app.setStyleSheet(_GLOBAL_STYLE)

    _base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    _icon_path = os.path.join(_base, "assets", "icon.png")
    if os.path.exists(_icon_path):
        app.setWindowIcon(QIcon(_icon_path))

    from app.utils.app_config import is_first_run
    if is_first_run():
        wiz = FirstRunWizard()
        if wiz.exec() != FirstRunWizard.DialogCode.Accepted:
            sys.exit(0)

    from app.database.connection import get_engine, reset_engine
    while True:
        try:
            get_engine()
            break
        except Exception as e:
            QMessageBox.critical(
                None, "DB接続エラー",
                f"データベースに接続できませんでした。\n\n{e}\n\n設定を確認してください。")
            reset_engine()
            dlg = FirstRunWizard(is_initial_setup=False)
            if dlg.exec() != FirstRunWizard.DialogCode.Accepted:
                sys.exit(0)

    dlg = LoginDialog()
    if dlg.exec() != LoginDialog.DialogCode.Accepted:
        sys.exit(0)

    from app.database.connection import get_session
    from app.services.send_job_service import delete_old_jobs
    session = get_session()
    try:
        delete_old_jobs(session)
    except Exception:
        pass
    finally:
        session.close()

    window = MainWindow(staff_name=dlg.staff_name(), readonly=dlg.readonly())
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
