from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QComboBox, QPushButton, QLabel, QTabWidget, QMessageBox,
)
from app.database.connection import get_session
from app.services.meeting_service import get_meetings, create_meeting, delete_meeting
from app.services.position_service import get_positions
from app.ui.dialogs.new_meeting_dialog import NewMeetingDialog
from app.ui.meeting_widgets.preentry_widget import PreentryWidget
from app.ui.meeting_widgets.reception_widget import ReceptionWidget
from app.ui.meeting_widgets.log_widget import LogWidget


class MeetingTab(QWidget):
    def __init__(self, staff_name: str = "", readonly: bool = False):
        super().__init__()
        self._staff_name = staff_name
        self._readonly = readonly
        self._current_meeting_id: int | None = None
        self._build()
        self._load_meetings()

    def _build(self):
        layout = QVBoxLayout(self)

        hdr = QHBoxLayout()
        hdr.addWidget(QLabel("会議:"))
        self._meeting_combo = QComboBox()
        self._meeting_combo.currentIndexChanged.connect(self._on_meeting_select)
        hdr.addWidget(self._meeting_combo, 1)
        if not self._readonly:
            btn_new = QPushButton("新規作成")
            btn_new.clicked.connect(self._create_meeting)
            btn_del = QPushButton("削除")
            btn_del.clicked.connect(self._delete_meeting)
            hdr.addWidget(btn_new)
            hdr.addWidget(btn_del)
        layout.addLayout(hdr)

        self._preentry = PreentryWidget(readonly=self._readonly)
        self._reception = ReceptionWidget(
            staff_name=self._staff_name, readonly=self._readonly)
        self._log = LogWidget()

        self._inner = QTabWidget()
        self._inner.addTab(self._preentry, "事前入力")
        self._inner.addTab(self._reception, "当日受付")
        self._inner.addTab(self._log, "受付ログ")
        self._inner.currentChanged.connect(self._on_inner_tab_change)
        layout.addWidget(self._inner)

    def _load_meetings(self):
        session = get_session()
        try:
            meetings = get_meetings(session)
        finally:
            session.close()
        self._meeting_combo.blockSignals(True)
        self._meeting_combo.clear()
        self._meeting_combo.addItem("（会議を選択してください）", None)
        for m in meetings:
            scope = "全員" if not m.target_position_ids else "役職指定"
            self._meeting_combo.addItem(
                f"{m.date.strftime('%Y/%m/%d')}　{m.name}　（{scope}）", m.id)
        self._meeting_combo.blockSignals(False)
        if meetings:
            self._meeting_combo.setCurrentIndex(1)
        else:
            self._current_meeting_id = None

    def _on_meeting_select(self):
        self._current_meeting_id = self._meeting_combo.currentData()
        self._preentry.load(self._current_meeting_id)
        if self._inner.currentIndex() == 1:
            self._reception.load(self._current_meeting_id)

    def _on_inner_tab_change(self, idx: int):
        mid = self._current_meeting_id
        if idx == 1:
            self._reception.load(mid)
            self._reception.start_timer()
        elif idx == 2:
            self._reception.stop_timer()
            self._log.load(mid)
        else:
            self._reception.stop_timer()

    def _create_meeting(self):
        session = get_session()
        try:
            positions = get_positions(session)
        finally:
            session.close()
        dlg = NewMeetingDialog(positions, self)
        if dlg.exec():
            name, meeting_date, target_ids = dlg.get_values()
            session = get_session()
            try:
                create_meeting(session, name, meeting_date, target_ids)
            finally:
                session.close()
            self._load_meetings()

    def _delete_meeting(self):
        if not self._current_meeting_id:
            return
        ret = QMessageBox.question(
            self, "削除確認",
            f"会議「{self._meeting_combo.currentText()}」を削除しますか？\n"
            "出欠データもすべて削除されます。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if ret != QMessageBox.StandardButton.Yes:
            return
        session = get_session()
        try:
            delete_meeting(session, self._current_meeting_id)
        finally:
            session.close()
        self._current_meeting_id = None
        self._load_meetings()
