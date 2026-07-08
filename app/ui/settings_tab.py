# app/ui/settings_tab.py
import os

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QTabWidget, QFormLayout, QHBoxLayout,
    QLineEdit, QPushButton, QGroupBox, QTableWidget, QTableWidgetItem,
    QCheckBox, QMessageBox, QHeaderView, QLabel, QRadioButton, QButtonGroup,
    QFileDialog, QInputDialog, QTextEdit,
)
from PyQt6.QtCore import Qt
from app.utils.app_config import get_config, save_config, get_db_type, get_pg_config, get_html_export_path
from app.database.connection import get_session
from app.services.signature_service import (
    get_signatures, create_signature, update_signature,
    delete_signature, set_default
)
from app.services.staff_service import get_all_staff, create_staff, set_active


class SettingsTab(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        inner = QTabWidget()
        inner.addTab(_GraphSettingsWidget(), "Microsoft 365")
        inner.addTab(_SignatureWidget(), "署名管理")
        inner.addTab(_StaffWidget(), "職員管理")
        inner.addTab(_DbSettingsWidget(), "データベース接続")
        inner.addTab(_ExportSettingsWidget(), "出力設定")
        if os.environ.get("CCI_MAIL_DEV_TOOLS") == "1":
            inner.addTab(_DataWidget(), "データ管理")
        layout.addWidget(inner)


class _GraphSettingsWidget(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        grp = QGroupBox("Microsoft 365 / Graph API 設定")
        form = QFormLayout(grp)
        self._tenant_id = QLineEdit()
        self._client_id = QLineEdit()
        self._test_address = QLineEdit()
        form.addRow("テナントID", self._tenant_id)
        form.addRow("クライアントID", self._client_id)
        form.addRow("テスト送信先", self._test_address)
        layout.addWidget(grp)
        btn_row = QHBoxLayout()
        btn_save = QPushButton("設定を保存")
        btn_save.clicked.connect(self._save)
        btn_test = QPushButton("接続テスト")
        btn_test.clicked.connect(self._test_connection)
        btn_row.addWidget(btn_save)
        btn_row.addWidget(btn_test)
        btn_row.addStretch()
        layout.addLayout(btn_row)
        self._status_label = QLabel("")
        layout.addWidget(self._status_label)
        layout.addStretch()
        self._load()

    def _load(self):
        cfg = get_config().get("graph", {})
        self._tenant_id.setText(cfg.get("tenant_id", ""))
        self._client_id.setText(cfg.get("client_id", ""))
        self._test_address.setText(cfg.get("test_address", ""))

    def _save(self):
        config = get_config()
        config["graph"] = {
            "tenant_id":  self._tenant_id.text().strip(),
            "client_id":  self._client_id.text().strip(),
            "test_address": self._test_address.text().strip(),
        }
        save_config(config)
        from app.ui.widgets.inline_status import show_inline_message
        show_inline_message(self._status_label, "設定を保存しました")

    def _test_connection(self):
        self._save()
        try:
            from app.services.email_service import get_access_token
            get_access_token(get_config().get("graph", {}))
            QMessageBox.information(self, "成功", "Microsoft 365への接続に成功しました。")
        except Exception as e:
            QMessageBox.critical(self, "エラー", str(e))


class _SignatureWidget(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        self._table = QTableWidget(0, 2)
        self._table.setHorizontalHeaderLabels(["署名名", "デフォルト"])
        self._table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.itemSelectionChanged.connect(self._on_select)
        layout.addWidget(self._table)

        form = QFormLayout()
        self._name = QLineEdit()
        self._body = QTextEdit()
        self._body.setPlaceholderText("署名本文（複数行入力可）")
        self._body.setMaximumHeight(140)
        form.addRow("署名名", self._name)
        form.addRow("本文", self._body)
        layout.addLayout(form)

        btn_row = QHBoxLayout()
        btn_add = QPushButton("追加")
        btn_add.clicked.connect(self._add)
        btn_update = QPushButton("更新")
        btn_update.clicked.connect(self._update)
        btn_delete = QPushButton("削除")
        btn_delete.clicked.connect(self._delete)
        btn_default = QPushButton("デフォルトに設定")
        btn_default.clicked.connect(self._set_default)
        btn_row.addWidget(btn_add)
        btn_row.addWidget(btn_update)
        btn_row.addWidget(btn_delete)
        btn_row.addWidget(btn_default)
        btn_row.addStretch()
        layout.addLayout(btn_row)
        self._load()

    def _load(self):
        session = get_session()
        try:
            self._signatures = get_signatures(session)
        finally:
            session.close()
        self._table.setRowCount(0)
        for s in self._signatures:
            row = self._table.rowCount()
            self._table.insertRow(row)
            self._table.setItem(row, 0, QTableWidgetItem(s.name))
            self._table.setItem(row, 1, QTableWidgetItem("●" if s.is_default else ""))
            self._table.item(row, 0).setData(Qt.ItemDataRole.UserRole, s.id)

    def _on_select(self):
        row = self._table.currentRow()
        if row < 0 or row >= len(self._signatures):
            return
        s = self._signatures[row]
        self._name.setText(s.name)
        self._body.setPlainText(s.body)

    def _selected_id(self) -> int | None:
        row = self._table.currentRow()
        if row < 0:
            return None
        return self._table.item(row, 0).data(Qt.ItemDataRole.UserRole)

    def _add(self):
        name = self._name.text().strip()
        body = self._body.toPlainText()
        if not name:
            QMessageBox.warning(self, "入力エラー", "署名名を入力してください。")
            return
        session = get_session()
        create_signature(session, name, body)
        session.close()
        self._load()

    def _update(self):
        sig_id = self._selected_id()
        if sig_id is None:
            return
        name = self._name.text().strip()
        body = self._body.toPlainText()
        if not name:
            QMessageBox.warning(self, "入力エラー", "署名名を入力してください。")
            return
        session = get_session()
        update_signature(session, sig_id, name=name, body=body)
        session.close()
        self._load()

    def _delete(self):
        sig_id = self._selected_id()
        if sig_id is None:
            return
        ret = QMessageBox.question(
            self, "削除確認", "この署名を削除しますか？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if ret != QMessageBox.StandardButton.Yes:
            return
        session = get_session()
        delete_signature(session, sig_id)
        session.close()
        self._load()

    def _set_default(self):
        sig_id = self._selected_id()
        if sig_id is None:
            return
        session = get_session()
        set_default(session, sig_id)
        session.close()
        self._load()


class _StaffWidget(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        self._table = QTableWidget(0, 2)
        self._table.setHorizontalHeaderLabels(["職員名", "有効"])
        self._table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self._table)

        form = QFormLayout()
        self._name = QLineEdit()
        form.addRow("職員名", self._name)
        layout.addLayout(form)

        btn_row = QHBoxLayout()
        btn_add = QPushButton("追加")
        btn_add.clicked.connect(self._add)
        btn_toggle = QPushButton("有効/無効切り替え")
        btn_toggle.clicked.connect(self._toggle)
        btn_row.addWidget(btn_add)
        btn_row.addWidget(btn_toggle)
        btn_row.addStretch()
        layout.addLayout(btn_row)
        self._load()

    def _load(self):
        session = get_session()
        try:
            self._staff = get_all_staff(session)
        finally:
            session.close()
        self._table.setRowCount(0)
        for s in self._staff:
            row = self._table.rowCount()
            self._table.insertRow(row)
            self._table.setItem(row, 0, QTableWidgetItem(s.name))
            self._table.setItem(row, 1, QTableWidgetItem("○" if s.is_active else "×"))
            self._table.item(row, 0).setData(Qt.ItemDataRole.UserRole, s.id)

    def _add(self):
        name = self._name.text().strip()
        if not name:
            QMessageBox.warning(self, "入力エラー", "職員名を入力してください。")
            return
        session = get_session()
        create_staff(session, name)
        session.close()
        self._name.clear()
        self._load()

    def _toggle(self):
        row = self._table.currentRow()
        if row < 0 or row >= len(self._staff):
            return
        s = self._staff[row]
        session = get_session()
        set_active(session, s.id, not s.is_active)
        session.close()
        self._load()


class _DbSettingsWidget(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)

        # DB種別選択
        type_grp = QGroupBox("データベースの種類")
        type_layout = QHBoxLayout(type_grp)
        self._rb_sqlite = QRadioButton("SQLite（ローカル・1台用）")
        self._rb_pg     = QRadioButton("PostgreSQL（ネットワーク・複数台用）")
        self._type_group = QButtonGroup(self)
        self._type_group.addButton(self._rb_sqlite, 0)
        self._type_group.addButton(self._rb_pg, 1)
        type_layout.addWidget(self._rb_sqlite)
        type_layout.addWidget(self._rb_pg)
        type_layout.addStretch()
        layout.addWidget(type_grp)

        # PostgreSQL接続設定
        self._pg_grp = QGroupBox("PostgreSQL接続設定")
        pg_form = QFormLayout(self._pg_grp)
        self._pg_host = QLineEdit()
        self._pg_port = QLineEdit()
        self._pg_port.setFixedWidth(80)
        self._pg_db   = QLineEdit()
        self._pg_user = QLineEdit()
        self._pg_pass = QLineEdit()
        self._pg_pass.setEchoMode(QLineEdit.EchoMode.Password)
        pg_form.addRow("ホスト名 / IPアドレス", self._pg_host)
        pg_form.addRow("ポート番号",             self._pg_port)
        pg_form.addRow("データベース名",          self._pg_db)
        pg_form.addRow("ユーザー名",              self._pg_user)
        pg_form.addRow("パスワード",              self._pg_pass)
        layout.addWidget(self._pg_grp)

        # ボタン行
        btn_row = QHBoxLayout()
        btn_test = QPushButton("接続テスト")
        btn_test.clicked.connect(self._test_connection)
        btn_save = QPushButton("設定を保存（要再起動）")
        btn_save.clicked.connect(self._save)
        btn_row.addWidget(btn_test)
        btn_row.addWidget(btn_save)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        layout.addWidget(QLabel(
            "※ 設定を保存後、アプリを再起動すると新しい接続先が有効になります。"))
        layout.addStretch()

        self._type_group.idToggled.connect(self._on_type_toggle)
        self._load()

    def _load(self):
        db_type = get_db_type()
        if db_type == "postgresql":
            self._rb_pg.setChecked(True)
        else:
            self._rb_sqlite.setChecked(True)
        pg = get_pg_config()
        self._pg_host.setText(pg.get("host", "localhost"))
        self._pg_port.setText(str(pg.get("port", "5432")))
        self._pg_db.setText(pg.get("database", "cci_mail"))
        self._pg_user.setText(pg.get("user", ""))
        self._pg_pass.setText(pg.get("password", ""))
        self._pg_grp.setEnabled(self._rb_pg.isChecked())

    def _on_type_toggle(self, btn_id: int, checked: bool):
        if checked:
            self._pg_grp.setEnabled(btn_id == 1)

    def _test_connection(self):
        if self._rb_sqlite.isChecked():
            QMessageBox.information(self, "接続テスト", "SQLiteはローカルファイルのため接続テスト不要です。")
            return
        try:
            from sqlalchemy import create_engine, text
            from sqlalchemy.engine import URL as SaURL
            url = SaURL.create(
                "postgresql+psycopg2",
                username=self._pg_user.text().strip(),
                password=self._pg_pass.text(),
                host=self._pg_host.text().strip(),
                port=int(self._pg_port.text().strip() or "5432"),
                database=self._pg_db.text().strip(),
            )
            engine = create_engine(url, connect_args={"connect_timeout": 5})
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            engine.dispose()
            QMessageBox.information(self, "接続テスト成功",
                                    "PostgreSQLへの接続に成功しました。")
        except Exception as e:
            QMessageBox.critical(self, "接続テスト失敗", str(e))

    def _save(self):
        config = get_config()
        config["db_type"] = "postgresql" if self._rb_pg.isChecked() else "sqlite"
        config["postgresql"] = {
            "host":     self._pg_host.text().strip(),
            "port":     self._pg_port.text().strip() or "5432",
            "database": self._pg_db.text().strip(),
            "user":     self._pg_user.text().strip(),
            "password": self._pg_pass.text(),
        }
        save_config(config)
        QMessageBox.information(self, "保存完了",
                                "設定を保存しました。\nアプリを再起動すると新しい接続先が有効になります。")


class _ExportSettingsWidget(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)

        grp = QGroupBox("出欠状況 HTML 出力")
        form = QFormLayout(grp)

        path_row = QHBoxLayout()
        self._path_edit = QLineEdit()
        self._path_edit.setPlaceholderText("例: \\\\server\\share\\出欠状況.html")
        btn_browse = QPushButton("参照...")
        btn_browse.setFixedWidth(72)
        btn_browse.clicked.connect(self._browse)
        path_row.addWidget(self._path_edit)
        path_row.addWidget(btn_browse)
        form.addRow("出力先ファイル", path_row)
        layout.addWidget(grp)

        layout.addWidget(QLabel(
            "受付操作のたびに自動更新されます。\n"
            "共有フォルダに保存すれば、他のPCのブラウザで出欠状況を確認できます。\n"
            "空白のままにすると HTML 出力は行われません。"))

        btn_row = QHBoxLayout()
        btn_save = QPushButton("設定を保存")
        btn_save.clicked.connect(self._save)
        btn_export = QPushButton("今すぐ出力")
        btn_export.clicked.connect(self._export_now)
        btn_row.addWidget(btn_save)
        btn_row.addWidget(btn_export)
        btn_row.addStretch()
        layout.addLayout(btn_row)
        self._status_label = QLabel("")
        layout.addWidget(self._status_label)
        layout.addStretch()
        self._load()

    def _load(self):
        self._path_edit.setText(get_html_export_path())

    def _browse(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "HTML出力先を選択", self._path_edit.text() or "出欠状況.html",
            "HTML ファイル (*.html *.htm)")
        if path:
            self._path_edit.setText(path)

    def _save(self):
        config = get_config()
        config["html_export_path"] = self._path_edit.text().strip()
        save_config(config)
        from app.ui.widgets.inline_status import show_inline_message
        show_inline_message(self._status_label, "設定を保存しました")

    def _export_now(self):
        path = self._path_edit.text().strip()
        if not path:
            QMessageBox.warning(self, "エラー", "出力先ファイルを設定してください。")
            return
        try:
            from app.services.html_export_service import export_attendance_html
            export_attendance_html(path)
            QMessageBox.information(self, "出力完了", f"HTML を出力しました。\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "エラー", str(e))


class _DataWidget(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)

        grp = QGroupBox("会員データ一括削除（開発用）")
        grp_layout = QVBoxLayout(grp)
        grp_layout.addWidget(QLabel(
            "全会員データを完全に削除します。\n"
            "この操作は取り消せません。開発・テスト時のみ使用してください。"
        ))
        btn = QPushButton("一括削除を実行")
        btn.setStyleSheet("color: #DC2626; border: 1px solid #DC2626;")
        btn.clicked.connect(self._bulk_delete)
        grp_layout.addWidget(btn)
        layout.addWidget(grp)
        layout.addStretch()

    def _bulk_delete(self):
        from app.database.connection import get_session
        from app.database.models import (
            Member, EmailAddress, MemberHistory,
            AttendanceRecord, ReceptionLog, SendLog,
        )
        ret = QMessageBox.warning(
            self, "一括削除（開発用）",
            "全会員データを完全に削除します。\nこの操作は取り消せません。\n\n本当に実行しますか？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if ret != QMessageBox.StandardButton.Yes:
            return
        text, ok = QInputDialog.getText(
            self, "最終確認",
            "削除を実行するには「DELETE」と入力してください：",
        )
        if not ok or text.strip() != "DELETE":
            QMessageBox.information(self, "キャンセル", "削除をキャンセルしました。")
            return
        session = get_session()
        try:
            session.query(ReceptionLog).delete()
            session.query(AttendanceRecord).delete()
            session.query(SendLog).filter(SendLog.member_id.isnot(None)).update(
                {"member_id": None}, synchronize_session=False)
            session.query(MemberHistory).delete()
            session.query(EmailAddress).delete()
            session.query(Member).delete()
            session.commit()
            QMessageBox.information(self, "完了", "全会員データを削除しました。")
        except Exception as e:
            session.rollback()
            QMessageBox.critical(self, "エラー", str(e))
        finally:
            session.close()
