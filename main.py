import sys
import os
from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtGui import QIcon, QFont
from app.ui.main_window import MainWindow
from app.ui.dialogs.login_dialog import LoginDialog
from app.ui.dialogs.first_run_wizard import FirstRunWizard
from app.ui.theme import apply_theme


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("cci-mail")
    _font = app.font()
    _font.setPointSizeF(10.5)
    app.setFont(_font)
    apply_theme(app)

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
            from app.utils.db_errors import format_connection_error
            QMessageBox.critical(
                None, "DB接続エラー",
                f"データベースに接続できませんでした。\n\n{format_connection_error(e)}\n\n設定を確認してください。")
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
