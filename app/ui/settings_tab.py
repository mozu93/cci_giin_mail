# app/ui/settings_tab.py
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QTabWidget, QFormLayout, QHBoxLayout,
    QLineEdit, QPushButton, QGroupBox, QTableWidget, QTableWidgetItem,
    QCheckBox, QMessageBox, QHeaderView, QLabel, QRadioButton, QButtonGroup
)
from PyQt6.QtCore import Qt
from app.utils.app_config import get_config, save_config, get_db_type, get_pg_config
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
        layout.addWidget(inner)


class _GraphSettingsWidget(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        grp = QGroupBox("Microsoft 365 / Graph API 設定")
        form = QFormLayout(grp)
        self._tenant_id = QLineEdit()
        self._client_id = QLineEdit()
        self._client_secret = QLineEdit()
        self._client_secret.setEchoMode(QLineEdit.EchoMode.Password)
        self._from_address = QLineEdit()
        self._test_address = QLineEdit()
        form.addRow("テナントID", self._tenant_id)
        form.addRow("クライアントID", self._client_id)
        form.addRow("クライアントシークレット", self._client_secret)
        form.addRow("送信元アドレス", self._from_address)
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
        layout.addStretch()
        self._load()

    def _load(self):
        cfg = get_config().get("graph", {})
        self._tenant_id.setText(cfg.get("tenant_id", ""))
        self._client_id.setText(cfg.get("client_id", ""))
        self._client_secret.setText(cfg.get("client_secret", ""))
        self._from_address.setText(cfg.get("from_address", ""))
        self._test_address.setText(cfg.get("test_address", ""))

    def _save(self):
        config = get_config()
        config["graph"] = {
            "tenant_id":     self._tenant_id.text().strip(),
            "client_id":     self._client_id.text().strip(),
            "client_secret": self._client_secret.text(),
            "from_address":  self._from_address.text().strip(),
            "test_address":  self._test_address.text().strip(),
        }
        save_config(config)
        QMessageBox.information(self, "保存", "設定を保存しました。")

    def _test_connection(self):
        self._save()
        try:
            import msal
            cfg = get_config().get("graph", {})
            app = msal.ConfidentialClientApplication(
                cfg["client_id"],
                authority=f"https://login.microsoftonline.com/{cfg['tenant_id']}",
                client_credential=cfg["client_secret"],
            )
            result = app.acquire_token_for_client(
                scopes=["https://graph.microsoft.com/.default"]
            )
            if "access_token" in result:
                QMessageBox.information(self, "成功", "Microsoft 365への接続に成功しました。")
            else:
                QMessageBox.critical(self, "失敗",
                                     f"トークン取得失敗: {result.get('error_description', '')}")
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
        self._body = QLineEdit()
        self._body.setPlaceholderText("署名本文（複数行は\\nで区切る）")
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
        self._body.setText(s.body.replace("\n", "\\n"))

    def _selected_id(self) -> int | None:
        row = self._table.currentRow()
        if row < 0:
            return None
        return self._table.item(row, 0).data(Qt.ItemDataRole.UserRole)

    def _add(self):
        name = self._name.text().strip()
        body = self._body.text().replace("\\n", "\n")
        if not name:
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
        body = self._body.text().replace("\\n", "\n")
        session = get_session()
        update_signature(session, sig_id, name=name, body=body)
        session.close()
        self._load()

    def _delete(self):
        sig_id = self._selected_id()
        if sig_id is None:
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
