# app/ui/dialogs/member_edit_dialog.py
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QHBoxLayout,
    QLineEdit, QComboBox, QPushButton, QGroupBox,
    QScrollArea, QWidget, QLabel, QMessageBox
)
from PyQt6.QtCore import Qt
from sqlalchemy.orm import Session
from app.database.models import Member, Position
from app.services.member_service import (
    create_member, update_member, set_email_addresses
)

_MAX_EMAILS = 5


class MemberEditDialog(QDialog):
    def __init__(self, session: Session, member: Member | None = None,
                 staff_name: str = "", parent=None):
        super().__init__(parent)
        self._session = session
        self._member = member
        self._staff_name = staff_name
        self.setWindowTitle("会員編集" if member else "会員追加")
        self.setMinimumWidth(520)
        self._build()
        if member:
            self._load(member)

    def _build(self):
        layout = QVBoxLayout(self)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        form_layout = QVBoxLayout(inner)

        # 基本情報
        grp_basic = QGroupBox("基本情報")
        form = QFormLayout(grp_basic)
        self._member_number = QLineEdit()
        self._org_name = QLineEdit()
        self._org_kana = QLineEdit()
        self._title = QLineEdit()
        self._name = QLineEdit()
        self._name_kana = QLineEdit()
        self._position_combo = QComboBox()
        self._notes = QLineEdit()

        self._positions = self._session.query(Position).order_by(Position.sort_order).all()
        self._position_combo.addItem("（なし）", None)
        for p in self._positions:
            self._position_combo.addItem(p.name, p.id)

        form.addRow("会員番号 *", self._member_number)
        form.addRow("会議所役職", self._position_combo)
        form.addRow("事業所名 *", self._org_name)
        form.addRow("事業所名フリガナ", self._org_kana)
        form.addRow("役職名", self._title)
        form.addRow("氏名 *", self._name)
        form.addRow("氏名フリガナ", self._name_kana)
        form.addRow("備考", self._notes)
        form_layout.addWidget(grp_basic)

        # メールアドレス
        grp_email = QGroupBox("メールアドレス（最大5件）")
        email_layout = QFormLayout(grp_email)
        self._email_rows: list[tuple[QLineEdit, QLineEdit]] = []
        for i in range(1, _MAX_EMAILS + 1):
            addr = QLineEdit()
            addr.setPlaceholderText(f"アドレス{i}")
            label = QLineEdit()
            label.setPlaceholderText("ラベル（本人・総務等）")
            row_widget = QHBoxLayout()
            row_widget.addWidget(addr, 3)
            row_widget.addWidget(label, 1)
            container = QWidget()
            container.setLayout(row_widget)
            email_layout.addRow(f"メール{i}", container)
            self._email_rows.append((addr, label))
        form_layout.addWidget(grp_email)

        # 変更理由（編集時のみ表示）
        self._reason_widget = QGroupBox("変更理由")
        reason_form = QFormLayout(self._reason_widget)
        self._change_reason = QLineEdit()
        self._change_reason.setPlaceholderText("変更理由を入力してください（必須）")
        reason_form.addRow("理由", self._change_reason)
        form_layout.addWidget(self._reason_widget)
        if not self._member:
            self._reason_widget.setVisible(False)

        scroll.setWidget(inner)
        layout.addWidget(scroll)

        # ボタン
        btn_row = QHBoxLayout()
        btn_cancel = QPushButton("キャンセル")
        btn_cancel.clicked.connect(self.reject)
        btn_save = QPushButton("保存")
        btn_save.setDefault(True)
        btn_save.clicked.connect(self._save)
        btn_row.addWidget(btn_cancel)
        btn_row.addStretch()
        btn_row.addWidget(btn_save)
        layout.addLayout(btn_row)

    def _load(self, member: Member):
        self._member_number.setText(member.member_number)
        self._member_number.setReadOnly(True)
        self._org_name.setText(member.organization_name)
        self._org_kana.setText(member.organization_kana or "")
        self._title.setText(member.title or "")
        self._name.setText(member.name)
        self._name_kana.setText(member.name_kana or "")
        self._notes.setText(member.notes or "")
        for i, p in enumerate(self._positions):
            if p.id == member.position_id:
                self._position_combo.setCurrentIndex(i + 1)
                break
        for i, ea in enumerate(member.email_addresses[:_MAX_EMAILS]):
            self._email_rows[i][0].setText(ea.address)
            self._email_rows[i][1].setText(ea.label or "")

    def _save(self):
        member_number = self._member_number.text().strip()
        org_name = self._org_name.text().strip()
        name = self._name.text().strip()
        if not member_number or not org_name or not name:
            QMessageBox.warning(self, "入力エラー",
                                "会員番号・事業所名・氏名は必須です。")
            return
        if self._member and not self._change_reason.text().strip():
            QMessageBox.warning(self, "入力エラー", "変更理由を入力してください。")
            return

        position_id = self._position_combo.currentData()
        addresses = []
        for i, (addr_w, label_w) in enumerate(self._email_rows, start=1):
            addr = addr_w.text().strip()
            if addr:
                addresses.append({
                    "address":    addr,
                    "label":      label_w.text().strip(),
                    "sort_order": i,
                })

        try:
            if self._member:
                update_member(
                    self._session, self._member.id,
                    changed_by=self._staff_name,
                    change_reason=self._change_reason.text().strip(),
                    organization_name=org_name,
                    organization_kana=self._org_kana.text().strip(),
                    title=self._title.text().strip(),
                    name=name,
                    name_kana=self._name_kana.text().strip(),
                    notes=self._notes.text().strip(),
                    position_id=position_id,
                )
                set_email_addresses(self._session, self._member.id, addresses)
                self._session.commit()
            else:
                m = create_member(
                    self._session, member_number, org_name, name,
                    organization_kana=self._org_kana.text().strip(),
                    title=self._title.text().strip(),
                    name_kana=self._name_kana.text().strip(),
                    notes=self._notes.text().strip(),
                    position_id=position_id,
                )
                set_email_addresses(self._session, m.id, addresses)
                self._session.commit()
        except Exception as e:
            QMessageBox.critical(self, "エラー", str(e))
            return
        self.accept()
