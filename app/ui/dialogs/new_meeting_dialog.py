from datetime import date
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLineEdit, QDateEdit, QPushButton, QGroupBox,
    QRadioButton, QButtonGroup, QCheckBox, QMessageBox, QWidget
)
from PyQt6.QtCore import QDate


class NewMeetingDialog(QDialog):
    def __init__(self, positions: list, committees: list | None = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("会議作成")
        self.setMinimumWidth(340)
        layout = QVBoxLayout(self)

        form = QFormLayout()
        self._name = QLineEdit()
        self._name.setPlaceholderText("例: 第50回定時総会")
        self._date = QDateEdit(QDate.currentDate())
        self._date.setCalendarPopup(True)
        self._date.setDisplayFormat("yyyy/MM/dd")
        form.addRow("会議名", self._name)
        form.addRow("開催日", self._date)
        layout.addLayout(form)

        target_grp = QGroupBox("対象者")
        target_layout = QVBoxLayout(target_grp)
        self._rb_all = QRadioButton("全員（総会など）")
        self._rb_pos = QRadioButton("役職指定（常議員会など）")
        self._rb_committee = QRadioButton("委員会指定")
        self._rb_all.setChecked(True)
        btn_grp = QButtonGroup(self)
        btn_grp.addButton(self._rb_all)
        btn_grp.addButton(self._rb_pos)
        btn_grp.addButton(self._rb_committee)
        target_layout.addWidget(self._rb_all)
        target_layout.addWidget(self._rb_pos)
        target_layout.addWidget(self._rb_committee)

        self._pos_widget = QWidget()
        pos_layout = QVBoxLayout(self._pos_widget)
        pos_layout.setContentsMargins(20, 0, 0, 0)
        self._pos_checks: dict[int, QCheckBox] = {}
        for p in positions:
            cb = QCheckBox(p.name)
            pos_layout.addWidget(cb)
            self._pos_checks[p.id] = cb
        self._pos_widget.setVisible(False)
        target_layout.addWidget(self._pos_widget)

        self._committee_widget = QWidget()
        committee_layout = QVBoxLayout(self._committee_widget)
        committee_layout.setContentsMargins(20, 0, 0, 0)
        self._committee_checks: dict[int, QCheckBox] = {}
        for c in (committees or []):
            cb = QCheckBox(c.name)
            committee_layout.addWidget(cb)
            self._committee_checks[c.id] = cb
        self._committee_widget.setVisible(False)
        target_layout.addWidget(self._committee_widget)
        layout.addWidget(target_grp)

        self._rb_pos.toggled.connect(self._pos_widget.setVisible)
        self._rb_committee.toggled.connect(self._committee_widget.setVisible)

        btn_row = QHBoxLayout()
        btn_cancel = QPushButton("キャンセル")
        btn_cancel.clicked.connect(self.reject)
        btn_ok = QPushButton("作成")
        btn_ok.clicked.connect(self._ok)
        btn_ok.setDefault(True)
        btn_row.addWidget(btn_cancel)
        btn_row.addWidget(btn_ok)
        layout.addLayout(btn_row)

    def _ok(self):
        if not self._name.text().strip():
            QMessageBox.warning(self, "エラー", "会議名を入力してください。")
            return
        if self._rb_pos.isChecked() and not any(
                cb.isChecked() for cb in self._pos_checks.values()):
            QMessageBox.warning(self, "エラー", "役職を1つ以上選択してください。")
            return
        if self._rb_committee.isChecked() and not any(
                cb.isChecked() for cb in self._committee_checks.values()):
            QMessageBox.warning(self, "エラー", "委員会を1つ以上選択してください。")
            return
        self.accept()

    def get_values(self) -> tuple[str, date, list[int] | None, list[int] | None]:
        d = self._date.date()
        target_position_ids = None
        target_committee_ids = None
        if self._rb_pos.isChecked():
            target_position_ids = [pid for pid, cb in self._pos_checks.items()
                                   if cb.isChecked()]
        elif self._rb_committee.isChecked():
            target_committee_ids = [cid for cid, cb in self._committee_checks.items()
                                    if cb.isChecked()]
        return (self._name.text().strip(), date(d.year(), d.month(), d.day()),
                target_position_ids, target_committee_ids)
