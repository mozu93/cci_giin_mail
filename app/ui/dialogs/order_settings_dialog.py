from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout,
    QListWidget, QListWidgetItem, QPushButton, QLabel, QMessageBox
)
from PyQt6.QtCore import Qt
from sqlalchemy.orm import Session
from app.database.models import Position, Member


class OrderSettingsDialog(QDialog):
    """副会頭の就任順を設定するダイアログ

    役職そのものの表示順（sort_order）は設定タブの「役職・委員会管理」に統合済み。
    """

    def __init__(self, session: Session, parent=None):
        super().__init__(parent)
        self._session = session
        self.setWindowTitle("副会頭の就任順設定")
        self.resize(500, 400)
        self._build()
        self._load()

    def _build(self):
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel(
            "副会頭を就任が古い順（上）→新しい順（下）に並べ替えてください。\n"
            "（ドラッグまたは ↑↓ ボタンで操作）"))
        self._fuku_list = QListWidget()
        self._fuku_list.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        layout.addWidget(self._fuku_list)
        layout.addLayout(self._arrow_buttons(self._fuku_list))

        # 保存 / キャンセル
        btns = QHBoxLayout()
        btn_save   = QPushButton("保存")
        btn_cancel = QPushButton("キャンセル")
        btn_save.clicked.connect(self._save)
        btn_cancel.clicked.connect(self.reject)
        btns.addStretch()
        btns.addWidget(btn_save)
        btns.addWidget(btn_cancel)
        layout.addLayout(btns)

    def _arrow_buttons(self, list_widget: QListWidget) -> QHBoxLayout:
        row = QHBoxLayout()
        btn_up   = QPushButton("↑ 上へ")
        btn_down = QPushButton("↓ 下へ")
        btn_up.clicked.connect(lambda: self._move(list_widget, -1))
        btn_down.clicked.connect(lambda: self._move(list_widget, +1))
        row.addStretch()
        row.addWidget(btn_up)
        row.addWidget(btn_down)
        return row

    @staticmethod
    def _move(lw: QListWidget, delta: int):
        row = lw.currentRow()
        if row < 0:
            return
        new_row = row + delta
        if new_row < 0 or new_row >= lw.count():
            return
        item = lw.takeItem(row)
        lw.insertItem(new_row, item)
        lw.setCurrentRow(new_row)

    def _load(self):
        positions = (self._session.query(Position)
                     .order_by(Position.sort_order, Position.id)
                     .all())

        # 副会頭を display_order → organization_kana 順に表示
        fuku_pos = next(
            (p for p in positions if "副会頭" in p.name), None)
        self._fuku_list.clear()
        if fuku_pos:
            members = (self._session.query(Member)
                       .filter_by(position_id=fuku_pos.id, is_active=True)
                       .order_by(Member.display_order.asc().nullslast(),
                                 Member.organization_kana)
                       .all())
            for m in members:
                label = f"{m.organization_name}　{m.name}"
                item = QListWidgetItem(label)
                item.setData(Qt.ItemDataRole.UserRole, m.id)
                self._fuku_list.addItem(item)
        else:
            self._fuku_list.addItem("（副会頭の役職が登録されていません）")

    def _save(self):
        # 副会頭の display_order を保存
        for i in range(self._fuku_list.count()):
            item = self._fuku_list.item(i)
            member_id = item.data(Qt.ItemDataRole.UserRole)
            if member_id is None:
                continue
            m = self._session.get(Member, member_id)
            if m:
                m.display_order = i + 1

        self._session.commit()
        QMessageBox.information(self, "保存完了", "表示順を保存しました。")
        self.accept()
