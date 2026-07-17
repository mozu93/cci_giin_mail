from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit,
    QPushButton, QLabel, QTableWidget, QTableWidgetItem, QHeaderView,
    QComboBox, QMessageBox,
)
from app.database.connection import get_session
from app.services.member_service import get_members
from app.services.attendance_mail_service import (
    fetch_messages, build_preview, commit_rows, get_since_datetime)
from app.utils.app_config import (
    get_attendance_mail_folder, save_attendance_mail_folder,
    get_attendance_mail_subject_filter, save_attendance_mail_subject_filter,
)
from app.ui.dialogs.attendance_mail_alias_dialog import AttendanceMailAliasDialog


class _NoWheelComboBox(QComboBox):
    def wheelEvent(self, event):
        event.ignore()


class AttendanceMailImportDialog(QDialog):
    _COL_ORG = 0
    _COL_NAME = 1
    _COL_STATUS = 2
    _COL_PROXY = 3
    _COL_NOTES = 4
    _COL_EXISTING = 5
    _COL_MEMBER = 6

    def __init__(self, meeting_id: int, graph_config: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("メールから出欠を取り込む")
        self.resize(1180, 560)
        self._meeting_id = meeting_id
        self._graph_config = graph_config
        self._rows = []
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            "Outlookで仕分けした対象フォルダから、常議員会の出欠連絡メールを取り込みます。"))

        form = QFormLayout()
        self._folder_input = QLineEdit(get_attendance_mail_folder())
        form.addRow("対象フォルダ名", self._folder_input)
        self._subject_input = QLineEdit(get_attendance_mail_subject_filter())
        form.addRow("対象件名（部分一致・空欄可）", self._subject_input)
        layout.addLayout(form)

        btn_row = QHBoxLayout()
        btn_search = QPushButton("検索")
        btn_search.clicked.connect(self._search)
        btn_row.addWidget(btn_search)
        btn_row.addStretch()
        btn_aliases = QPushButton("事業所名の紐付けを管理...")
        btn_aliases.clicked.connect(self._open_alias_dialog)
        btn_row.addWidget(btn_aliases)
        layout.addLayout(btn_row)

        self._table = QTableWidget(0, 7)
        self._table.setHorizontalHeaderLabels([
            "事業所名（メール記載）", "氏名", "出欠", "代理役職・代理者名",
            "備考", "既存の登録", "会員"])
        self._table.setColumnWidth(self._COL_ORG, 180)
        self._table.setColumnWidth(self._COL_NAME, 110)
        self._table.setColumnWidth(self._COL_STATUS, 60)
        self._table.setColumnWidth(self._COL_PROXY, 160)
        self._table.setColumnWidth(self._COL_NOTES, 140)
        self._table.setColumnWidth(self._COL_EXISTING, 120)
        self._table.horizontalHeader().setSectionResizeMode(
            self._COL_MEMBER, QHeaderView.ResizeMode.Stretch)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self._table)

        self._status_label = QLabel("（未検索）")
        layout.addWidget(self._status_label)

        btn_close = QHBoxLayout()
        btn_apply = QPushButton("反映")
        btn_apply.clicked.connect(self._apply)
        btn_cancel = QPushButton("キャンセル")
        btn_cancel.clicked.connect(self.reject)
        btn_close.addStretch()
        btn_close.addWidget(btn_cancel)
        btn_close.addWidget(btn_apply)
        layout.addLayout(btn_close)

    def _search(self):
        folder_name = self._folder_input.text().strip()
        if not folder_name:
            QMessageBox.warning(self, "入力エラー", "対象フォルダ名を入力してください。")
            return
        subject_filter = self._subject_input.text().strip()
        save_attendance_mail_folder(folder_name)
        save_attendance_mail_subject_filter(subject_filter)

        session = get_session()
        try:
            from app.database.models import ProcessedAttendanceMail
            processed_ids = {
                r.message_id for r in
                session.query(ProcessedAttendanceMail).all()
            }
            since = get_since_datetime(session, self._meeting_id)
            try:
                messages = fetch_messages(
                    self._graph_config, folder_name, subject_filter, processed_ids, since)
            except (ValueError, RuntimeError) as e:
                QMessageBox.critical(self, "エラー", str(e))
                return
            self._rows = build_preview(session, self._meeting_id, messages)
            members = get_members(session, active_only=True)
            self._refresh_table(members)
        finally:
            session.close()

        self._status_label.setText(f"{len(self._rows)} 件のメールを読み込みました。")

    def _open_alias_dialog(self):
        dlg = AttendanceMailAliasDialog(parent=self)
        dlg.exec()

    def _refresh_table(self, members):
        self._table.setRowCount(0)
        for row in self._rows:
            r = self._table.rowCount()
            self._table.insertRow(r)
            self._table.setItem(r, self._COL_ORG, QTableWidgetItem(row.org_name_raw))
            self._table.setItem(r, self._COL_NAME, QTableWidgetItem(row.name_raw))
            self._table.setItem(r, self._COL_STATUS, QTableWidgetItem(row.status))
            proxy_text = (f"{row.proxy_title} {row.proxy_name}".strip()
                         if (row.proxy_title or row.proxy_name) else "")
            self._table.setItem(r, self._COL_PROXY, QTableWidgetItem(proxy_text))
            self._table.setItem(r, self._COL_NOTES, QTableWidgetItem(row.notes))
            existing_text = (f"{row.existing_status} → {row.status}"
                            if row.existing_status and row.existing_status != row.status
                            else (row.existing_status or ""))
            self._table.setItem(r, self._COL_EXISTING, QTableWidgetItem(existing_text))

            combo = _NoWheelComboBox()
            combo.addItem("（会員未選択）", None)
            selected_index = 0
            for i, m in enumerate(members, start=1):
                combo.addItem(f"{m.organization_name}（{m.name}）", m.id)
                if row.matched_member is not None and m.id == row.matched_member.id:
                    selected_index = i
            combo.setCurrentIndex(selected_index)
            if selected_index == 0:
                combo.setStyleSheet("background-color: #FEE2E2;")
            self._table.setCellWidget(r, self._COL_MEMBER, combo)

    def _apply(self):
        selected_member_by_index = {}
        for r in range(self._table.rowCount()):
            combo = self._table.cellWidget(r, self._COL_MEMBER)
            member_id = combo.currentData()
            if member_id is not None:
                selected_member_by_index[r] = member_id

        session = get_session()
        try:
            result = commit_rows(
                session, self._meeting_id, self._rows, selected_member_by_index)
        finally:
            session.close()

        QMessageBox.information(
            self, "取り込み完了",
            f"反映: {result['applied']}件 / 未選択のためスキップ: {result['skipped']}件")
        self.accept()
