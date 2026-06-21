# app/ui/member_tab.py
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QScrollArea, QGridLayout,
    QPushButton, QLineEdit, QComboBox, QLabel, QFrame, QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSignal
from app.database.connection import get_session
from app.database.models import Position
from app.services.member_service import get_members, delete_member


class _MemberCard(QFrame):
    """1会員分の情報を表示するカードウィジェット"""
    clicked = pyqtSignal(int)
    double_clicked = pyqtSignal(int)

    _NORMAL   = "QFrame{background:white;border:1px solid #D1D5DB;border-radius:6px;}"
    _SELECTED = "QFrame{background:#EFF6FF;border:2px solid #1D4ED8;border-radius:6px;}"

    def __init__(self, member, parent=None):
        super().__init__(parent)
        self._member_id = member.id
        self.setStyleSheet(self._NORMAL)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(108)
        self._build(member)

    def _build(self, member):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 7, 10, 7)
        layout.setSpacing(2)

        # 1行目: 会員番号 ／ 会議所役職
        row1 = QHBoxLayout()
        lbl_num = QLabel(f"#{member.member_number}")
        lbl_num.setStyleSheet("color:#6B7280;font-size:11px;")
        pos_name = member.position.name if member.position else ""
        lbl_pos = QLabel(pos_name)
        lbl_pos.setStyleSheet("color:#1D4ED8;font-size:11px;font-weight:bold;")
        row1.addWidget(lbl_num)
        row1.addStretch()
        row1.addWidget(lbl_pos)
        layout.addLayout(row1)

        # 2行目: 事業所名
        lbl_org = QLabel(member.organization_name)
        lbl_org.setStyleSheet("font-size:13px;font-weight:bold;color:#111827;")
        layout.addWidget(lbl_org)

        # 3行目: 役職名＋氏名
        title_str = f"{member.title}　" if member.title else ""
        lbl_person = QLabel(f"{title_str}{member.name}")
        lbl_person.setStyleSheet("font-size:12px;color:#374151;")
        layout.addWidget(lbl_person)

        # 4行目: メール1（なければ空行）
        if member.email_addresses:
            lbl_mail = QLabel(member.email_addresses[0].address)
            lbl_mail.setStyleSheet("font-size:10px;color:#6B7280;")
        else:
            lbl_mail = QLabel("")
        layout.addWidget(lbl_mail)

        # 5行目: 最終更新日
        upd = member.updated_at.strftime("%Y/%m/%d") if member.updated_at else ""
        lbl_upd = QLabel(f"更新: {upd}")
        lbl_upd.setStyleSheet("font-size:10px;color:#9CA3AF;")
        layout.addWidget(lbl_upd)

    def set_selected(self, selected: bool):
        self.setStyleSheet(self._SELECTED if selected else self._NORMAL)

    def mousePressEvent(self, event):
        self.clicked.emit(self._member_id)
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        self.double_clicked.emit(self._member_id)
        super().mouseDoubleClickEvent(event)


class MemberTab(QWidget):
    def __init__(self):
        super().__init__()
        self._staff_name = ""
        self._selected_id: int | None = None
        self._cards: dict[int, _MemberCard] = {}
        self._all_members: list = []
        self._build()
        self._load()

    def set_staff_name(self, name: str):
        self._staff_name = name

    def _build(self):
        layout = QVBoxLayout(self)

        # ツールバー
        toolbar = QHBoxLayout()
        self._search = QLineEdit()
        self._search.setPlaceholderText("キーワード検索（事業所名・氏名・会員番号・フリガナ）")
        self._search.textChanged.connect(self._apply_filter)
        self._pos_filter = QComboBox()
        self._pos_filter.addItem("すべての役職", None)
        self._pos_filter.currentIndexChanged.connect(self._apply_filter)
        btn_add     = QPushButton("追加")
        btn_edit    = QPushButton("編集")
        btn_delete  = QPushButton("退任")
        btn_history = QPushButton("変更履歴")
        btn_import  = QPushButton("インポート")
        btn_add.clicked.connect(self._add)
        btn_edit.clicked.connect(self._edit)
        btn_delete.clicked.connect(self._delete)
        btn_history.clicked.connect(self._show_history)
        btn_import.clicked.connect(self._import)
        toolbar.addWidget(self._search, 2)
        toolbar.addWidget(QLabel("役職:"))
        toolbar.addWidget(self._pos_filter)
        toolbar.addStretch()
        toolbar.addWidget(btn_add)
        toolbar.addWidget(btn_edit)
        toolbar.addWidget(btn_delete)
        toolbar.addWidget(btn_history)
        toolbar.addWidget(btn_import)
        layout.addLayout(toolbar)

        # 2カラムカードグリッド
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._cards_widget = QWidget()
        self._grid = QGridLayout(self._cards_widget)
        self._grid.setHorizontalSpacing(8)
        self._grid.setVerticalSpacing(8)
        self._grid.setContentsMargins(4, 4, 4, 4)
        self._scroll.setWidget(self._cards_widget)
        layout.addWidget(self._scroll)

        self._count_label = QLabel("")
        layout.addWidget(self._count_label)

    def _load_positions(self):
        session = get_session()
        try:
            positions = session.query(Position).order_by(Position.sort_order).all()
            current = self._pos_filter.currentData()
            self._pos_filter.blockSignals(True)
            self._pos_filter.clear()
            self._pos_filter.addItem("すべての役職", None)
            for p in positions:
                self._pos_filter.addItem(p.name, p.id)
            self._pos_filter.blockSignals(False)
            if current is not None:
                for i in range(self._pos_filter.count()):
                    if self._pos_filter.itemData(i) == current:
                        self._pos_filter.setCurrentIndex(i)
                        break
        finally:
            session.close()

    def _load(self):
        """DBから全会員を読み込み直す（追加・編集・インポート後に呼ぶ）"""
        self._load_positions()
        self._selected_id = None
        session = get_session()
        try:
            self._all_members = get_members(session, active_only=True)
        finally:
            session.close()
        self._apply_filter()

    def _apply_filter(self):
        """フィルタを適用してカードグリッドを再描画する"""
        keyword = self._search.text().strip().lower()
        pos_id  = self._pos_filter.currentData()

        visible = [m for m in self._all_members
                   if self._matches(m, keyword, pos_id)]

        # グリッドをクリア（ウィジェットを破棄）
        while self._grid.count():
            item = self._grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._cards.clear()

        for i, m in enumerate(visible):
            card = _MemberCard(m)
            card.clicked.connect(self._on_card_click)
            card.double_clicked.connect(self._edit_by_id)
            self._cards[m.id] = card
            self._grid.addWidget(card, i // 2, i % 2)

        # 奇数件数のとき右列にスペーサーを置いて左寄せを維持
        if len(visible) % 2 == 1:
            spc = QWidget()
            spc.setFixedHeight(108)
            self._grid.addWidget(spc, len(visible) // 2, 1)

        self._count_label.setText(f"{len(visible)} 件")

    def _matches(self, m, keyword: str, pos_id) -> bool:
        if pos_id is not None and m.position_id != pos_id:
            return False
        if keyword:
            targets = [
                m.organization_name.lower(),
                (m.organization_kana or "").lower(),
                m.name.lower(),
                (m.name_kana or "").lower(),
                m.member_number.lower(),
            ]
            if not any(keyword in t for t in targets):
                return False
        return True

    def _selected_member_id(self) -> int | None:
        return self._selected_id

    def _on_card_click(self, member_id: int):
        if self._selected_id is not None and self._selected_id in self._cards:
            self._cards[self._selected_id].set_selected(False)
        self._selected_id = member_id
        if member_id in self._cards:
            self._cards[member_id].set_selected(True)

    def _add(self):
        from app.ui.dialogs.member_edit_dialog import MemberEditDialog
        session = get_session()
        dlg = MemberEditDialog(session, staff_name=self._staff_name, parent=self)
        if dlg.exec():
            self._load()
        session.close()

    def _edit(self):
        member_id = self._selected_member_id()
        if member_id is None:
            QMessageBox.information(self, "選択なし", "会員カードをクリックして選択してください。")
            return
        self._edit_by_id(member_id)

    def _edit_by_id(self, member_id: int):
        from app.ui.dialogs.member_edit_dialog import MemberEditDialog
        from app.services.member_service import get_member
        session = get_session()
        member = get_member(session, member_id)
        dlg = MemberEditDialog(session, member=member,
                               staff_name=self._staff_name, parent=self)
        if dlg.exec():
            self._load()
        session.close()

    def _delete(self):
        member_id = self._selected_member_id()
        if member_id is None:
            QMessageBox.information(self, "選択なし", "会員カードをクリックして選択してください。")
            return
        ret = QMessageBox.question(
            self, "退任処理確認",
            "この会員を退任処理しますか？\n一覧から非表示になりますが、変更履歴は保持されます。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if ret != QMessageBox.StandardButton.Yes:
            return
        session = get_session()
        delete_member(session, member_id, changed_by=self._staff_name)
        session.close()
        self._load()

    def _show_history(self):
        member_id = self._selected_member_id()
        if member_id is None:
            QMessageBox.information(self, "選択なし", "会員カードをクリックして選択してください。")
            return
        from app.ui.dialogs.member_history_dialog import MemberHistoryDialog
        session = get_session()
        dlg = MemberHistoryDialog(session, member_id, parent=self)
        dlg.exec()
        session.close()

    def _import(self):
        from app.ui.dialogs.import_dialog import ImportDialog
        session = get_session()
        dlg = ImportDialog(session, staff_name=self._staff_name, parent=self)
        if dlg.exec():
            self._load()
        session.close()
