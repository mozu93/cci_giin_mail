# app/ui/template_tab.py
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QListWidget, QListWidgetItem, QPushButton,
    QFormLayout, QLineEdit, QTextEdit, QComboBox,
    QLabel, QGroupBox, QMessageBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeySequence, QShortcut
from app.database.connection import get_session
from app.services.template_service import (
    get_templates, create_template, update_template, delete_template
)
from app.services.signature_service import get_signatures

_PLACEHOLDERS = [
    "{事業所名}", "{役職名}", "{氏名}", "{会議所役職名}",
    "{col1}", "{col2}", "{col3}", "{col4}", "{col5}",
]


class TemplateTab(QWidget):
    def __init__(self):
        super().__init__()
        self._current_id: int | None = None
        self._snapshot: tuple = ("", "", "", None)
        self._build()
        self._load()



    def _build(self):
        layout = QVBoxLayout(self)
        QShortcut(QKeySequence("Ctrl+S"), self).activated.connect(self._save)
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # 左ペイン：テンプレート一覧
        left = QWidget()
        left_layout = QVBoxLayout(left)
        self._list = QListWidget()
        self._list.currentRowChanged.connect(self._on_select)
        btn_row = QHBoxLayout()
        btn_new = QPushButton("新規")
        btn_new.clicked.connect(self._new)
        btn_delete = QPushButton("削除")
        btn_delete.clicked.connect(self._delete)
        btn_row.addWidget(btn_new)
        btn_row.addWidget(btn_delete)
        left_layout.addWidget(QLabel("テンプレート一覧"))
        left_layout.addWidget(self._list)
        left_layout.addLayout(btn_row)
        self._empty_hint = QLabel(
            "テンプレートがまだありません。「新規」ボタンから作成してください。")
        self._empty_hint.setWordWrap(True)
        self._empty_hint.setStyleSheet("color: #64748B; padding: 4px;")
        self._empty_hint.setVisible(False)
        left_layout.addWidget(self._empty_hint)
        splitter.addWidget(left)

        # 右ペイン：編集フォーム
        right = QWidget()
        right_layout = QVBoxLayout(right)
        form_grp = QGroupBox("テンプレート編集")
        form = QFormLayout(form_grp)
        self._name = QLineEdit()
        self._subject = QLineEdit()
        self._body = QTextEdit()
        self._body.setMinimumHeight(200)
        self._sig_combo = QComboBox()
        form.addRow("テンプレート名", self._name)
        form.addRow("件名", self._subject)
        form.addRow("本文", self._body)
        form.addRow("デフォルト署名", self._sig_combo)
        right_layout.addWidget(form_grp)

        ph_grp = QGroupBox("使用可能なプレースホルダー（クリックで本文に挿入）")
        ph_layout = QVBoxLayout(ph_grp)
        btn_row = QHBoxLayout()
        for ph in _PLACEHOLDERS:
            btn = QPushButton(ph)
            btn.setFlat(True)
            btn.setStyleSheet(
                "font-size: 12px; color: #1E40AF; padding: 2px 6px;"
                "border: 1px solid #BFDBFE; border-radius: 3px;")
            btn.clicked.connect(lambda checked, p=ph: self._insert_placeholder(p))
            btn_row.addWidget(btn)
        btn_row.addStretch()
        ph_layout.addLayout(btn_row)
        ph_layout.addWidget(QLabel(
            "差し込みデータ: {col1}〜{col5}は送信時にCSV/Excelからインポートした値に置換されます"))
        right_layout.addWidget(ph_grp)

        btn_save = QPushButton("保存")
        btn_save.clicked.connect(self._save)
        right_layout.addWidget(btn_save)
        self._status_label = QLabel("")
        right_layout.addWidget(self._status_label)
        splitter.addWidget(right)

        splitter.setSizes([200, 500])
        layout.addWidget(splitter)

    def _load(self):
        session = get_session()
        try:
            self._templates = get_templates(session)
            self._signatures = get_signatures(session)
        finally:
            session.close()

        self._list.blockSignals(True)
        self._list.clear()
        for t in self._templates:
            item = QListWidgetItem(t.name)
            item.setData(Qt.ItemDataRole.UserRole, t.id)
            self._list.addItem(item)
        self._list.blockSignals(False)

        self._sig_combo.blockSignals(True)
        self._sig_combo.clear()
        self._sig_combo.addItem("（なし）", None)
        for s in self._signatures:
            self._sig_combo.addItem(s.name, s.id)
        self._sig_combo.blockSignals(False)

        self._empty_hint.setVisible(len(self._templates) == 0)

    def _on_select(self, row: int):
        if row < 0 or row >= len(self._templates):
            return
        if not self._confirm_discard():
            self._list.blockSignals(True)
            self._select_row_for_id(self._current_id)
            self._list.blockSignals(False)
            return
        t = self._templates[row]
        self._current_id = t.id
        self._name.setText(t.name)
        self._subject.setText(t.subject)
        self._body.setPlainText(t.body)
        for i in range(self._sig_combo.count()):
            if self._sig_combo.itemData(i) == t.signature_id:
                self._sig_combo.setCurrentIndex(i)
                break
        self._take_snapshot()

    def _select_row_for_id(self, template_id: int | None):
        for i, t in enumerate(self._templates):
            if t.id == template_id:
                self._list.setCurrentRow(i)
                return
        self._list.clearSelection()

    def _take_snapshot(self):
        self._snapshot = (
            self._name.text(), self._subject.text(),
            self._body.toPlainText(), self._sig_combo.currentData())

    def _is_dirty(self) -> bool:
        current = (
            self._name.text(), self._subject.text(),
            self._body.toPlainText(), self._sig_combo.currentData())
        return current != self._snapshot

    def _confirm_discard(self) -> bool:
        if not self._is_dirty():
            return True
        ret = QMessageBox.question(
            self, "未保存の変更",
            "編集中の内容が保存されていません。破棄しますか？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        return ret == QMessageBox.StandardButton.Yes

    def _insert_placeholder(self, placeholder: str):
        self._body.setFocus()
        self._body.insertPlainText(placeholder)

    def _new(self):
        if not self._confirm_discard():
            return
        self._clear_form()

    def _clear_form(self):
        self._current_id = None
        self._name.clear()
        self._subject.clear()
        self._body.clear()
        self._sig_combo.setCurrentIndex(0)
        self._list.clearSelection()
        self._take_snapshot()

    def _save(self):
        name = self._name.text().strip()
        subject = self._subject.text().strip()
        body = self._body.toPlainText().strip()
        if not name or not subject:
            QMessageBox.warning(self, "入力エラー", "テンプレート名と件名は必須です。")
            return
        sig_id = self._sig_combo.currentData()
        session = get_session()
        try:
            if self._current_id:
                update_template(session, self._current_id,
                                name=name, subject=subject,
                                body=body, signature_id=sig_id)
            else:
                create_template(session, name, subject, body,
                                signature_id=sig_id)
        except Exception as e:
            QMessageBox.critical(self, "エラー", str(e))
            return
        finally:
            session.close()
        from app.ui.widgets.inline_status import show_inline_message
        show_inline_message(self._status_label, "テンプレートを保存しました")
        self._load()
        self._take_snapshot()

    def _delete(self):
        if self._current_id is None:
            return
        ret = QMessageBox.question(
            self, "削除確認", "このテンプレートを削除しますか？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if ret != QMessageBox.StandardButton.Yes:
            return
        session = get_session()
        delete_template(session, self._current_id)
        session.close()
        self._clear_form()
        self._load()
