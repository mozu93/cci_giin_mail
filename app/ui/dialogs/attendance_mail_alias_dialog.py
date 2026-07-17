from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget,
    QTableWidgetItem, QHeaderView, QComboBox, QPushButton, QMessageBox,
)
from app.database.connection import get_session
from app.services.member_service import get_members
from app.services.attendance_mail_service import (
    list_aliases, delete_alias, update_alias_member)


class _NoWheelComboBox(QComboBox):
    def wheelEvent(self, event):
        event.ignore()


class AttendanceMailAliasDialog(QDialog):
    """事業所名テキスト→会員 の紐付け一覧を確認・修正・削除するダイアログ。

    メール取り込みで一度確定した紐付けは次回以降自動適用されるが、
    誤って登録された場合はここで会員を選び直すか削除できる。
    """

    _COL_ORG = 0
    _COL_MEMBER = 1
    _COL_DELETE = 2

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("事業所名の紐付け管理")
        self.resize(820, 480)
        self._build()
        self._reload()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            "メールの出欠取り込みで確定した「事業所名の表記→会員」の紐付け一覧です。\n"
            "誤って登録された場合は会員を選び直すか、削除して自動突合に戻せます。"))

        self._table = QTableWidget(0, 3)
        self._table.setHorizontalHeaderLabels(
            ["事業所名（メール記載）", "紐付け先の会員", ""])
        self._table.setColumnWidth(self._COL_ORG, 260)
        self._table.horizontalHeader().setSectionResizeMode(
            self._COL_MEMBER, QHeaderView.ResizeMode.Stretch)
        self._table.setColumnWidth(self._COL_DELETE, 72)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self._table)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_close = QPushButton("閉じる")
        btn_close.clicked.connect(self.accept)
        btn_row.addWidget(btn_close)
        layout.addLayout(btn_row)

    def _reload(self):
        session = get_session()
        try:
            aliases = list_aliases(session)
            members = get_members(session, active_only=True)
            self._render(aliases, members)
        finally:
            session.close()

    def _render(self, aliases, members):
        self._table.setRowCount(0)
        for alias in aliases:
            r = self._table.rowCount()
            self._table.insertRow(r)
            self._table.setItem(
                r, self._COL_ORG, QTableWidgetItem(alias.org_name_raw))

            combo = _NoWheelComboBox()
            selected_index = 0
            for i, m in enumerate(members):
                combo.addItem(f"{m.organization_name}（{m.name}）", m.id)
                if m.id == alias.member_id:
                    selected_index = i
            combo.setCurrentIndex(selected_index)
            combo.currentIndexChanged.connect(
                lambda _idx, a=alias.id, c=combo: self._on_member_changed(a, c))
            self._table.setCellWidget(r, self._COL_MEMBER, combo)

            btn_delete = QPushButton("削除")
            btn_delete.clicked.connect(
                lambda _checked, a=alias.id, org=alias.org_name_raw:
                    self._on_delete(a, org))
            self._table.setCellWidget(r, self._COL_DELETE, btn_delete)

    def _on_member_changed(self, alias_id: int, combo: QComboBox):
        member_id = combo.currentData()
        if member_id is None:
            return
        session = get_session()
        try:
            update_alias_member(session, alias_id, member_id)
        finally:
            session.close()

    def _on_delete(self, alias_id: int, org_name_raw: str):
        reply = QMessageBox.question(
            self, "削除確認",
            f"「{org_name_raw}」の紐付けを削除しますか？\n"
            "次回以降は自動突合ロジックで再判定されます。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if reply != QMessageBox.StandardButton.Yes:
            return
        session = get_session()
        try:
            delete_alias(session, alias_id)
        finally:
            session.close()
        self._reload()
