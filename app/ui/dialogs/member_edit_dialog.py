# app/ui/dialogs/member_edit_dialog.py
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QHBoxLayout,
    QLineEdit, QComboBox, QPushButton, QGroupBox,
    QScrollArea, QWidget, QLabel, QMessageBox, QFileDialog
)
from PyQt6.QtCore import Qt
from sqlalchemy.orm import Session
from app.database.models import Member, Position
from app.services.member_service import (
    create_member, update_member, set_email_addresses, record_member_history
)

_MAX_EMAILS = 5


class MemberEditDialog(QDialog):
    def __init__(self, session: Session, member: Member | None = None,
                 staff_name: str = "", parent=None):
        super().__init__(parent)
        self._session = session
        self._member = member
        self._staff_name = staff_name
        self._photo_path: str | None = None
        self._photo_deleted: bool = False
        self._snapshot: tuple = ()
        self.setWindowTitle("会員編集" if member else "会員追加")
        self.setMinimumWidth(520)
        self._build()
        if member:
            self._load(member)
        self._take_snapshot()

    def _build(self):
        layout = QVBoxLayout(self)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        form_layout = QVBoxLayout(inner)

        # 顔写真
        grp_photo = QGroupBox("顔写真")
        photo_layout = QHBoxLayout(grp_photo)
        self._photo_label = QLabel("写真なし")
        self._photo_label.setFixedSize(90, 113)
        self._photo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._photo_label.setStyleSheet(
            "border: 1px solid #D1D5DB; background: #F3F4F6; color: #9CA3AF;")
        btn_photo_select = QPushButton("写真を選択")
        btn_photo_select.clicked.connect(self._select_photo)
        btn_photo_delete = QPushButton("削除")
        btn_photo_delete.clicked.connect(self._delete_photo)
        photo_btn_col = QVBoxLayout()
        photo_btn_col.addWidget(btn_photo_select)
        photo_btn_col.addWidget(btn_photo_delete)
        photo_btn_col.addStretch()
        photo_layout.addWidget(self._photo_label)
        photo_layout.addLayout(photo_btn_col)
        photo_layout.addStretch()
        form_layout.addWidget(grp_photo)

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

    def _select_photo(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "写真を選択", "",
            "画像ファイル (*.jpg *.jpeg *.png *.bmp)")
        if not path:
            return
        self._photo_path = path
        self._photo_deleted = False
        from PyQt6.QtGui import QPixmap
        from PyQt6.QtCore import Qt as _Qt
        pix = QPixmap(path).scaled(90, 113,
                                   _Qt.AspectRatioMode.KeepAspectRatio,
                                   _Qt.TransformationMode.SmoothTransformation)
        self._photo_label.setPixmap(pix)
        self._photo_label.setText("")

    def _delete_photo(self):
        self._photo_path = None
        self._photo_deleted = True
        self._photo_label.clear()
        self._photo_label.setText("写真なし")

    def _load(self, member: Member):
        self._member_number.setText(member.member_number)
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
        if member.photo_full:
            from app.services.photo_service import bytes_to_pixmap
            from PyQt6.QtCore import Qt as _Qt
            pix = bytes_to_pixmap(member.photo_full)
            if pix:
                pix = pix.scaled(90, 113,
                                 _Qt.AspectRatioMode.KeepAspectRatio,
                                 _Qt.TransformationMode.SmoothTransformation)
                self._photo_label.setPixmap(pix)
                self._photo_label.setText("")

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
                    member_number=member_number,
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
                saved_id = self._member.id
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
                record_member_history(self._session, m.id,
                                      changed_by=self._staff_name,
                                      change_reason="新規登録")
                saved_id = m.id

            from app.services.photo_service import save_photo, delete_photo
            if self._photo_deleted and self._member:
                delete_photo(self._session, saved_id)
            elif self._photo_path:
                save_photo(self._session, saved_id, self._photo_path)
        except Exception as e:
            QMessageBox.critical(self, "エラー", str(e))
            return
        self.accept()

    def _current_state(self) -> tuple:
        emails = tuple(
            (a.text().strip(), l.text().strip()) for a, l in self._email_rows)
        return (
            self._member_number.text().strip(),
            self._org_name.text().strip(),
            self._org_kana.text().strip(),
            self._title.text().strip(),
            self._name.text().strip(),
            self._name_kana.text().strip(),
            self._notes.text().strip(),
            self._position_combo.currentData(),
            emails,
        )

    def _take_snapshot(self):
        self._snapshot = self._current_state()

    def _is_dirty(self) -> bool:
        return self._current_state() != self._snapshot

    def reject(self):
        if self._is_dirty():
            ret = QMessageBox.question(
                self, "未保存の変更",
                "入力内容が保存されていません。破棄しますか？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No)
            if ret != QMessageBox.StandardButton.Yes:
                return
        super().reject()
