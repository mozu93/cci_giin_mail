# app/ui/settings_tab.py
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QTabWidget, QFormLayout, QHBoxLayout,
    QLineEdit, QPushButton, QGroupBox, QTableWidget, QTableWidgetItem,
    QCheckBox, QMessageBox, QHeaderView, QLabel, QSpinBox
)
from PyQt6.QtCore import Qt
from app.utils.app_config import get_config, save_config
from app.database.connection import get_session
from app.services.signature_service import (
    get_signatures, create_signature, update_signature,
    delete_signature, set_default
)
from app.services.position_service import (
    get_positions, create_position, update_position, delete_position
)
from app.services.staff_service import get_all_staff, create_staff, set_active


class SettingsTab(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        inner = QTabWidget()
        inner.addTab(_GraphSettingsWidget(), "Microsoft 365")
        inner.addTab(_SignatureWidget(), "署名管理")
        inner.addTab(_PositionWidget(), "会議所役職")
        inner.addTab(_StaffWidget(), "職員管理")
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


class _PositionWidget(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        self._table = QTableWidget(0, 2)
        self._table.setHorizontalHeaderLabels(["役職名", "表示順"])
        self._table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.itemSelectionChanged.connect(self._on_select)
        layout.addWidget(self._table)

        form = QFormLayout()
        self._name = QLineEdit()
        self._sort_order = QSpinBox()
        self._sort_order.setRange(0, 9999)
        form.addRow("役職名", self._name)
        form.addRow("表示順", self._sort_order)
        layout.addLayout(form)

        btn_row = QHBoxLayout()
        btn_add = QPushButton("追加")
        btn_add.clicked.connect(self._add)
        btn_update = QPushButton("更新")
        btn_update.clicked.connect(self._update)
        btn_delete = QPushButton("削除")
        btn_delete.clicked.connect(self._delete)
        btn_row.addWidget(btn_add)
        btn_row.addWidget(btn_update)
        btn_row.addWidget(btn_delete)
        btn_row.addStretch()
        layout.addLayout(btn_row)
        self._load()

    def _load(self):
        session = get_session()
        try:
            self._positions = get_positions(session)
        finally:
            session.close()
        self._table.setRowCount(0)
        for p in self._positions:
            row = self._table.rowCount()
            self._table.insertRow(row)
            self._table.setItem(row, 0, QTableWidgetItem(p.name))
            self._table.setItem(row, 1, QTableWidgetItem(str(p.sort_order)))
            self._table.item(row, 0).setData(Qt.ItemDataRole.UserRole, p.id)

    def _on_select(self):
        row = self._table.currentRow()
        if row < 0 or row >= len(self._positions):
            return
        p = self._positions[row]
        self._name.setText(p.name)
        self._sort_order.setValue(p.sort_order)

    def _selected_id(self) -> int | None:
        row = self._table.currentRow()
        if row < 0:
            return None
        return self._table.item(row, 0).data(Qt.ItemDataRole.UserRole)

    def _add(self):
        name = self._name.text().strip()
        if not name:
            return
        session = get_session()
        create_position(session, name, self._sort_order.value())
        session.close()
        self._load()

    def _update(self):
        pos_id = self._selected_id()
        if pos_id is None:
            return
        session = get_session()
        update_position(session, pos_id, name=self._name.text().strip(),
                        sort_order=self._sort_order.value())
        session.close()
        self._load()

    def _delete(self):
        pos_id = self._selected_id()
        if pos_id is None:
            return
        session = get_session()
        delete_position(session, pos_id)
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
