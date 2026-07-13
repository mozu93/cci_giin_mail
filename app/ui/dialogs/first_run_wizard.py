from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QComboBox, QSpinBox, QMessageBox, QFormLayout
)
from app.utils.app_config import get_config, save_config, get_pg_config


class FirstRunWizard(QDialog):
    def __init__(self, parent=None, is_initial_setup: bool = True):
        super().__init__(parent)
        self._is_initial_setup = is_initial_setup
        self.setWindowTitle("初期設定")
        self.setFixedSize(480, 340)
        self._build()
        self._load_current_config()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("データベースの接続先を設定してください。"))

        self._db_type = QComboBox()
        self._db_type.addItems(["PostgreSQL（複数人共有）", "SQLite（個人使用・開発用）"])
        self._db_type.currentIndexChanged.connect(self._on_type_change)

        form = QFormLayout()
        self._host = QLineEdit("localhost")
        self._port = QSpinBox()
        self._port.setRange(1, 65535)
        self._port.setValue(5432)
        self._database = QLineEdit("cci_mail")
        self._user = QLineEdit("postgres")
        self._password = QLineEdit()
        self._password.setEchoMode(QLineEdit.EchoMode.Password)

        form.addRow("DB種別", self._db_type)
        form.addRow("ホスト", self._host)
        form.addRow("ポート", self._port)
        form.addRow("データベース名", self._database)
        form.addRow("ユーザー名", self._user)
        form.addRow("パスワード", self._password)
        layout.addLayout(form)

        btn_row = QHBoxLayout()
        btn_test = QPushButton("接続テスト")
        btn_test.clicked.connect(self._test_connection)
        btn_label = "保存して開始" if self._is_initial_setup else "保存"
        btn_ok = QPushButton(btn_label)
        btn_ok.clicked.connect(self._save)
        btn_row.addWidget(btn_test)
        btn_row.addStretch()
        btn_row.addWidget(btn_ok)
        layout.addLayout(btn_row)

    def _load_current_config(self):
        # ウィザード自体の既定値は複数人共有のPostgreSQL。
        # get_db_type()（既存の1台用SQLite利用者との後方互換のため既定'sqlite'）は使わない。
        db_type = get_config().get("db_type", "postgresql")
        if db_type == "postgresql":
            self._db_type.setCurrentIndex(0)
            pg = get_pg_config()
            self._host.setText(pg.get("host", "localhost"))
            self._port.setValue(int(pg.get("port") or 5432))
            self._database.setText(pg.get("database", "cci_mail"))
            self._user.setText(pg.get("user", ""))
            self._password.setText(pg.get("password", ""))
        else:
            self._db_type.setCurrentIndex(1)
            self._on_type_change(1)

    def _on_type_change(self, index):
        is_pg = index == 0
        for w in [self._host, self._port, self._database, self._user, self._password]:
            w.setEnabled(is_pg)

    def _build_config(self) -> dict:
        """既存の設定にDB接続キーのみマージして返す（他の設定を消さない）。"""
        config = get_config()
        if self._db_type.currentIndex() == 0:
            config["db_type"] = "postgresql"
            config["postgresql"] = {
                "host":     self._host.text().strip(),
                "port":     str(self._port.value()),
                "database": self._database.text().strip(),
                "user":     self._user.text().strip(),
                "password": self._password.text(),
            }
        else:
            config["db_type"] = "sqlite"
        config["db_configured"] = True
        return config

    def _test_connection(self):
        if self._db_type.currentIndex() == 1:
            QMessageBox.information(self, "接続テスト", "SQLiteはローカルファイルのため接続テスト不要です。")
            return
        try:
            from sqlalchemy import create_engine, text
            from sqlalchemy.engine import URL as SaURL
            url = SaURL.create(
                "postgresql+psycopg2",
                username=self._user.text().strip(),
                password=self._password.text(),
                host=self._host.text().strip(),
                port=self._port.value(),
                database=self._database.text().strip(),
            )
            engine = create_engine(url, connect_args={"connect_timeout": 5})
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            engine.dispose()
            QMessageBox.information(self, "接続テスト成功", "PostgreSQLへの接続に成功しました。")
        except Exception as e:
            from app.utils.db_errors import format_connection_error
            QMessageBox.critical(self, "接続テスト失敗", format_connection_error(e))

    def _save(self):
        config = self._build_config()
        save_config(config)
        from app.database.connection import reset_engine, get_engine
        reset_engine()
        try:
            get_engine()
        except Exception as e:
            from app.utils.db_errors import format_connection_error
            QMessageBox.critical(self, "エラー",
                                 f"データベースに接続できませんでした。\n\n{format_connection_error(e)}")
            return
        if not self._is_initial_setup:
            QMessageBox.information(self, "保存完了", "DB接続設定を保存しました。")
        self.accept()
