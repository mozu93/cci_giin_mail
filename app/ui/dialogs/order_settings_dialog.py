from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget,
    QListWidget, QListWidgetItem, QPushButton, QLabel, QMessageBox
)
from PyQt6.QtCore import Qt
from sqlalchemy.orm import Session
from app.database.models import Position, Member


class OrderSettingsDialog(QDialog):
    """役職の表示順と副会頭の就任順を設定するダイアログ"""

    def __init__(self, session: Session, parent=None):
        super().__init__(parent)
        self._session = session
        self.setWindowTitle("表示順設定")
        self.resize(500, 460)
        self._build()
        self._load()

    def _build(self):
        layout = QVBoxLayout(self)

        self._tabs = QTabWidget()

        # ── Tab1: 役職の表示順 ──
        pos_widget = QWidget()
        pos_layout = QVBoxLayout(pos_widget)
        pos_layout.addWidget(QLabel(
            "役職を選択して ↑↓ ボタンで並べ替えてください。\n"
            "（例: 会頭→副会頭→常議員→監事→議員）"))
        self._pos_list = QListWidget()
        self._pos_list.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        pos_layout.addWidget(self._pos_list)
        pos_layout.addLayout(self._arrow_buttons(self._pos_list))
        self._tabs.addTab(pos_widget, "役職の表示順")

        # ── Tab2: 副会頭の就任順 ──
        fuku_widget = QWidget()
        fuku_layout = QVBoxLayout(fuku_widget)
        fuku_layout.addWidget(QLabel(
            "副会頭を就任が古い順（上）→新しい順（下）に並べ替えてください。\n"
            "（ドラッグまたは ↑↓ ボタンで操作）"))
        self._fuku_list = QListWidget()
        self._fuku_list.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        fuku_layout.addWidget(self._fuku_list)
        fuku_layout.addLayout(self._arrow_buttons(self._fuku_list))
        self._tabs.addTab(fuku_widget, "副会頭の就任順")

        layout.addWidget(self._tabs)

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
        # 役職を sort_order 順に表示
        positions = (self._session.query(Position)
                     .order_by(Position.sort_order, Position.id)
                     .all())
        self._pos_list.clear()
        for p in positions:
            item = QListWidgetItem(p.name)
            item.setData(Qt.ItemDataRole.UserRole, p.id)
            self._pos_list.addItem(item)

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
        # 役職の sort_order を保存
        for i in range(self._pos_list.count()):
            item = self._pos_list.item(i)
            pos_id = item.data(Qt.ItemDataRole.UserRole)
            if pos_id is None:
                continue
            pos = self._session.get(Position, pos_id)
            if pos:
                pos.sort_order = i + 1

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
