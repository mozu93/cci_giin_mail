# app/ui/send_tab.py
import os
import unicodedata
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QScrollArea,
    QGroupBox, QFormLayout, QComboBox, QLabel,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QPushButton, QCheckBox, QLineEdit, QTextEdit,
    QProgressBar, QFileDialog, QMessageBox,
    QListWidget, QListWidgetItem, QRadioButton, QButtonGroup
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QColor
from app.database.connection import get_session
from app.services.member_service import get_members
from app.services.template_service import get_templates, get_template
from app.services.signature_service import get_signatures, get_default_signature
from app.services.position_service import get_positions
from app.services.staff_service import get_staff_by_name
from app.services.email_service import render_body, send_mail, send_test_mail
from app.services.send_job_service import (
    create_job, start_job, finish_job, add_log
)
from app.utils.app_config import get_graph_config

_NO_EMAIL_TEXT = "（メール無し）"
_ORANGE = QColor("#F97316")


def _to_katakana(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    return "".join(
        chr(ord(ch) + 0x60) if 0x3041 <= ord(ch) <= 0x3096 else ch
        for ch in text
    )


class _SendWorker(QThread):
    progress = pyqtSignal(int, int, str)
    finished = pyqtSignal(int, int, int)

    def __init__(self, targets: list[dict], graph_config: dict,
                 job_id: int, session):
        super().__init__()
        self._targets = targets
        self._graph_config = graph_config
        self._job_id = job_id
        self._session = session

    def run(self):
        success = error = skip = 0
        total = len(self._targets)
        for i, t in enumerate(self._targets, 1):
            to_addr = t["to_address"]
            if not to_addr:
                add_log(self._session, self._job_id, t.get("member_id"),
                        "", t["subject"], "skip")
                skip += 1
                self.progress.emit(i, total, f"スキップ: {t['org_name']}")
                continue
            try:
                send_mail(
                    self._graph_config,
                    to_addr,
                    t["subject"],
                    t["body"],
                    t.get("attachments", []),
                )
                add_log(self._session, self._job_id, t.get("member_id"),
                        to_addr, t["subject"], "success")
                success += 1
                self.progress.emit(i, total, f"送信済: {t['org_name']}")
            except Exception as e:
                add_log(self._session, self._job_id, t.get("member_id"),
                        to_addr, t["subject"], "error", str(e))
                error += 1
                self.progress.emit(i, total, f"エラー: {t['org_name']} — {e}")
        self.finished.emit(success, error, skip)


class SendTab(QWidget):
    def __init__(self, staff_name: str = ""):
        super().__init__()
        self._staff_name = staff_name
        self._merge_data: dict[str, dict] = {}
        self._col_labels: dict[str, str] = {}
        self._common_attachments: list[str] = []
        self._individual_folder: str = ""
        self._attach_list: list[dict] = []
        self._members = []
        self._templates = []
        self._signatures = []
        self._build()

    # ──────────────────────────────────────────────────────
    # UI構築
    # ──────────────────────────────────────────────────────

    def _build(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(4, 4, 4, 4)
        main_layout.setSpacing(8)

        main_layout.addWidget(self._build_left_column())
        main_layout.addWidget(self._build_right_column(), 1)

        self._load_combos()

    def _build_left_column(self) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFixedWidth(370)

        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setSpacing(8)
        layout.setContentsMargins(4, 4, 4, 4)

        btn_clear = QPushButton("すべてクリア")
        btn_clear.clicked.connect(self._clear_all)
        layout.addWidget(btn_clear)

        layout.addWidget(self._build_step1())
        layout.addWidget(self._build_step2())
        layout.addWidget(self._build_step3())
        layout.addWidget(self._build_step4())
        layout.addWidget(self._build_step5())
        layout.addStretch()

        scroll.setWidget(inner)
        return scroll

    def _build_step1(self) -> QGroupBox:
        grp = QGroupBox("Step 1：宛先条件")
        layout = QVBoxLayout(grp)

        mode_row = QHBoxLayout()
        self._rb_by_pos = QRadioButton("役職で選ぶ")
        self._rb_by_attend = QRadioButton("会議の出欠で選ぶ")
        self._rb_by_pos.setChecked(True)
        bg = QButtonGroup(self)
        bg.addButton(self._rb_by_pos)
        bg.addButton(self._rb_by_attend)
        self._rb_by_pos.toggled.connect(self._on_mode_change)
        mode_row.addWidget(self._rb_by_pos)
        mode_row.addWidget(self._rb_by_attend)
        mode_row.addStretch()
        layout.addLayout(mode_row)

        # 役職パネル
        self._pos_panel = QWidget()
        pp = QVBoxLayout(self._pos_panel)
        pp.setContentsMargins(0, 0, 0, 0)
        pp.addWidget(QLabel("会議所役職（複数選択可 / Ctrl+クリック）："))
        self._pos_list = QListWidget()
        self._pos_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        self._pos_list.setMaximumHeight(100)
        self._pos_list.itemSelectionChanged.connect(self._on_pos_select)
        pp.addWidget(self._pos_list)
        layout.addWidget(self._pos_panel)

        # 会議出欠パネル
        self._attend_panel = QWidget()
        ap = QVBoxLayout(self._attend_panel)
        ap.setContentsMargins(0, 0, 0, 0)
        mrow = QHBoxLayout()
        mrow.addWidget(QLabel("会議:"))
        self._meeting_combo = QComboBox()
        self._meeting_combo.currentIndexChanged.connect(self._on_attend_filter)
        mrow.addWidget(self._meeting_combo, 1)
        ap.addLayout(mrow)
        srow = QHBoxLayout()
        srow.addWidget(QLabel("対象:"))
        self._status_checks: dict[str, QCheckBox] = {}
        for s in ["未回答", "欠席", "出席", "委任", "代理"]:
            cb = QCheckBox(s)
            cb.stateChanged.connect(self._on_attend_filter)
            srow.addWidget(cb)
            self._status_checks[s] = cb
        srow.addStretch()
        ap.addLayout(srow)
        self._attend_panel.setVisible(False)
        layout.addWidget(self._attend_panel)

        return grp

    def _build_step2(self) -> QGroupBox:
        grp = QGroupBox("Step 2：テンプレート・署名選択")
        f = QFormLayout(grp)
        self._template_combo = QComboBox()
        self._template_combo.currentIndexChanged.connect(self._on_template_select)
        self._sig_combo = QComboBox()
        self._subject_edit = QLineEdit()
        self._body_edit = QTextEdit()
        self._body_edit.setMaximumHeight(120)
        f.addRow("テンプレート", self._template_combo)
        f.addRow("署名", self._sig_combo)
        f.addRow("件名", self._subject_edit)
        f.addRow("本文", self._body_edit)
        return grp

    def _build_step3(self) -> QGroupBox:
        grp = QGroupBox("Step 3：差し込みデータ（任意）")
        layout = QVBoxLayout(grp)
        btn = QPushButton("CSV/Excelをインポート")
        btn.clicked.connect(self._import_merge)
        self._merge_status = QLabel("（未読み込み — col1〜col5は空で送信）")
        layout.addWidget(btn)
        layout.addWidget(self._merge_status)
        return grp

    def _build_step4(self) -> QGroupBox:
        grp = QGroupBox("Step 4：添付ファイル（任意）")
        layout = QVBoxLayout(grp)

        # 全社共通ファイル
        common_row = QHBoxLayout()
        btn_common = QPushButton("全社共通ファイルを選択")
        btn_common.clicked.connect(self._select_common_attach)
        btn_common_clear = QPushButton("クリア")
        btn_common_clear.setFixedWidth(52)
        btn_common_clear.clicked.connect(self._clear_common_attach)
        self._common_label = QLabel("（未選択）")
        self._common_label.setWordWrap(True)
        common_row.addWidget(btn_common)
        common_row.addWidget(btn_common_clear)
        common_row.addWidget(self._common_label, 1)
        layout.addLayout(common_row)

        # 会社別フォルダ
        layout.addWidget(QLabel(
            "会社別：会員番号に対応するファイルをフォルダから自動で添付します"))
        folder_row = QHBoxLayout()
        btn_folder = QPushButton("フォルダを選択")
        btn_folder.clicked.connect(self._select_indiv_folder)
        btn_folder_clear = QPushButton("クリア")
        btn_folder_clear.setFixedWidth(52)
        btn_folder_clear.clicked.connect(self._clear_indiv_folder)
        self._folder_label = QLabel("（未選択）")
        self._folder_label.setWordWrap(True)
        folder_row.addWidget(btn_folder)
        folder_row.addWidget(btn_folder_clear)
        folder_row.addWidget(self._folder_label, 1)
        layout.addLayout(folder_row)

        rule_row = QHBoxLayout()
        rule_row.addWidget(QLabel("ファイル名:"))
        self._rule_edit = QLineEdit("{会員番号}.pdf")
        self._rule_edit.setToolTip(
            "{会員番号} の部分に各会員番号が入ります。\n例: 会員番号が A001 なら → A001.pdf")
        rule_row.addWidget(self._rule_edit)
        btn_match = QPushButton("添付ファイルを確認・設定")
        btn_match.clicked.connect(self._check_matching)
        rule_row.addWidget(btn_match)
        layout.addLayout(rule_row)

        match_row = QHBoxLayout()
        self._match_label = QLabel("")
        match_row.addWidget(self._match_label)
        self._btn_show_attach = QPushButton("一覧を確認")
        self._btn_show_attach.setVisible(False)
        self._btn_show_attach.clicked.connect(self._show_attach_list)
        match_row.addWidget(self._btn_show_attach)
        layout.addLayout(match_row)

        return grp

    def _build_step5(self) -> QGroupBox:
        grp = QGroupBox("Step 5：最終確認・送信")
        layout = QVBoxLayout(grp)

        f = QFormLayout()
        self._job_name = QLineEdit()
        self._job_name.setPlaceholderText("例：2026年6月 総会案内")
        f.addRow("ジョブ名", self._job_name)
        layout.addLayout(f)

        btn_row = QHBoxLayout()
        btn_test = QPushButton("テスト送信（1通）")
        btn_test.clicked.connect(self._test_send)
        btn_preview = QPushButton("差し込みプレビュー")
        btn_preview.clicked.connect(self._show_send_preview)
        btn_send = QPushButton("送信実行")
        btn_send.setStyleSheet(
            "font-weight: bold; background-color: #1E40AF; color: white;")
        btn_send.clicked.connect(self._execute_send)
        btn_row.addWidget(btn_test)
        btn_row.addWidget(btn_preview)
        btn_row.addStretch()
        btn_row.addWidget(btn_send)
        layout.addLayout(btn_row)

        self._progress = QProgressBar()
        self._progress.setVisible(False)
        self._progress_label = QLabel("")
        layout.addWidget(self._progress)
        layout.addWidget(self._progress_label)
        return grp

    def _build_right_column(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(4)

        hdr = QHBoxLayout()
        hdr.addWidget(QLabel("<b>送信先一覧</b>"))
        hdr.addStretch()
        self._recipient_count_label = QLabel("0件選択")
        hdr.addWidget(self._recipient_count_label)
        layout.addLayout(hdr)

        search_row = QHBoxLayout()
        self._recipient_search = QLineEdit()
        self._recipient_search.setPlaceholderText("絞り込み（会員番号・事業所名・氏名）")
        self._recipient_search.textChanged.connect(self._filter_recipient_table)
        search_row.addWidget(self._recipient_search)
        btn_fd = QPushButton("A-")
        btn_fd.setFixedWidth(36)
        btn_fd.setToolTip("文字を小さくする")
        btn_fd.clicked.connect(lambda: self._adjust_font(-1))
        btn_fu = QPushButton("A+")
        btn_fu.setFixedWidth(36)
        btn_fu.setToolTip("文字を大きくする")
        btn_fu.clicked.connect(lambda: self._adjust_font(1))
        search_row.addWidget(btn_fd)
        search_row.addWidget(btn_fu)
        layout.addLayout(search_row)

        self._recipient_table = QTableWidget(0, 9)
        self._recipient_table.setHorizontalHeaderLabels(
            ["送信", "会員番号", "会議所役職名", "事業所名", "役職名", "氏名", "メールアドレス",
             "事業所名フリガナ", "氏名フリガナ"])
        h = self._recipient_table.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        for col in range(1, 7):
            h.setSectionResizeMode(col, QHeaderView.ResizeMode.Interactive)
        self._recipient_table.setColumnWidth(0, 44)
        self._recipient_table.setColumnWidth(1, 70)
        self._recipient_table.setColumnWidth(2, 110)
        self._recipient_table.setColumnWidth(3, 200)
        self._recipient_table.setColumnWidth(4, 90)
        self._recipient_table.setColumnWidth(5, 90)
        self._recipient_table.setColumnWidth(6, 200)
        self._recipient_table.setColumnHidden(7, True)
        self._recipient_table.setColumnHidden(8, True)
        self._recipient_table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers)
        self._recipient_table.setSelectionMode(
            QTableWidget.SelectionMode.NoSelection)

        from app.services.settings_service import get_font_size
        from PyQt6.QtGui import QFont as _QFont
        _sys_pt = self._recipient_table.font().pointSize()
        _saved_pt = get_font_size("send_tab", _sys_pt)
        _f = self._recipient_table.font()
        _f.setPointSize(_saved_pt)
        self._recipient_table.setFont(_f)
        self._recipient_table.verticalHeader().setDefaultSectionSize(
            self._recipient_table.verticalHeader().defaultSectionSize()
            + (_saved_pt - _sys_pt) * 2)

        layout.addWidget(self._recipient_table)

        self._no_email_label = QLabel("")
        self._no_email_label.setStyleSheet("color: #DC2626;")
        layout.addWidget(self._no_email_label)

        return widget

    # ──────────────────────────────────────────────────────
    # データ読み込み
    # ──────────────────────────────────────────────────────

    def _adjust_font(self, delta: int):
        from app.services.settings_service import set_font_size
        f = self._recipient_table.font()
        new_size = max(6, f.pointSize() + delta)
        f.setPointSize(new_size)
        self._recipient_table.setFont(f)
        vh = self._recipient_table.verticalHeader()
        vh.setDefaultSectionSize(max(20, vh.defaultSectionSize() + delta * 2))
        set_font_size("send_tab", new_size)

    def refresh(self):
        self._load_combos()

    def _load_combos(self):
        session = get_session()
        try:
            # 役職リスト
            self._pos_list.blockSignals(True)
            self._pos_list.clear()
            for p in get_positions(session):
                item = QListWidgetItem(p.name)
                item.setData(Qt.ItemDataRole.UserRole, p.id)
                self._pos_list.addItem(item)
            self._pos_list.blockSignals(False)

            # 会員リスト → 右カラムに展開
            self._members = get_members(session)
            self._recipient_table.setUpdatesEnabled(False)
            self._recipient_table.setRowCount(0)
            for m in self._members:
                self._append_recipient_row(m, checked=False)
            self._recipient_table.setUpdatesEnabled(True)
            self._update_recipient_count()

            # テンプレート
            self._templates = get_templates(session)
            self._template_combo.blockSignals(True)
            self._template_combo.clear()
            self._template_combo.addItem("（選択してください）", None)
            for t in self._templates:
                self._template_combo.addItem(t.name, t.id)
            self._template_combo.blockSignals(False)

            # 署名
            self._signatures = get_signatures(session)
            self._sig_combo.clear()
            self._sig_combo.addItem("（なし）", None)
            for s in self._signatures:
                self._sig_combo.addItem(s.name, s.id)
            default_sig = get_default_signature(session)
            if default_sig:
                for i in range(self._sig_combo.count()):
                    if self._sig_combo.itemData(i) == default_sig.id:
                        self._sig_combo.setCurrentIndex(i)
                        break
        finally:
            session.close()

    def _append_recipient_row(self, member, checked: bool):
        pos_name = member.position.name if member.position else ""
        org_kana = _to_katakana(member.organization_kana or "")
        name_kana = _to_katakana(member.name_kana or "")
        if member.email_addresses:
            for email in member.email_addresses:
                row = self._recipient_table.rowCount()
                self._recipient_table.insertRow(row)
                cb = QCheckBox()
                cb.setChecked(checked)
                cb.stateChanged.connect(self._update_recipient_count)
                self._recipient_table.setCellWidget(row, 0, cb)
                self._recipient_table.setItem(row, 1, QTableWidgetItem(member.member_number))
                self._recipient_table.setItem(row, 2, QTableWidgetItem(pos_name))
                org_item = QTableWidgetItem(member.organization_name)
                org_item.setData(Qt.ItemDataRole.UserRole, member.id)
                self._recipient_table.setItem(row, 3, org_item)
                self._recipient_table.setItem(row, 4, QTableWidgetItem(member.title or ""))
                self._recipient_table.setItem(row, 5, QTableWidgetItem(member.name))
                self._recipient_table.setItem(row, 6, QTableWidgetItem(email.address))
                self._recipient_table.setItem(row, 7, QTableWidgetItem(org_kana))
                self._recipient_table.setItem(row, 8, QTableWidgetItem(name_kana))
        else:
            row = self._recipient_table.rowCount()
            self._recipient_table.insertRow(row)
            cb = QCheckBox()
            cb.setChecked(checked)
            cb.stateChanged.connect(self._update_recipient_count)
            self._recipient_table.setCellWidget(row, 0, cb)
            self._recipient_table.setItem(row, 1, QTableWidgetItem(member.member_number))
            self._recipient_table.setItem(row, 2, QTableWidgetItem(pos_name))
            org_item = QTableWidgetItem(member.organization_name)
            org_item.setData(Qt.ItemDataRole.UserRole, member.id)
            self._recipient_table.setItem(row, 3, org_item)
            self._recipient_table.setItem(row, 4, QTableWidgetItem(member.title or ""))
            name_item = QTableWidgetItem(member.name)
            self._recipient_table.setItem(row, 5, name_item)
            addr_item = QTableWidgetItem(_NO_EMAIL_TEXT)
            addr_item.setForeground(_ORANGE)
            org_item.setForeground(_ORANGE)
            name_item.setForeground(_ORANGE)
            self._recipient_table.setItem(row, 6, addr_item)
            self._recipient_table.setItem(row, 7, QTableWidgetItem(org_kana))
            self._recipient_table.setItem(row, 8, QTableWidgetItem(name_kana))

    # ──────────────────────────────────────────────────────
    # 宛先フィルタリング
    # ──────────────────────────────────────────────────────

    def _clear_all(self):
        # 宛先
        self._rb_by_pos.setChecked(True)
        self._pos_list.clearSelection()
        for cb in self._status_checks.values():
            cb.setChecked(False)
        self._clear_recipient_checks()
        # テンプレート・本文
        self._template_combo.setCurrentIndex(0)
        self._sig_combo.setCurrentIndex(0)
        self._subject_edit.clear()
        self._body_edit.clear()
        # 差し込み
        self._merge_data = {}
        self._col_labels = {}
        self._merge_status.setText("（未読み込み — col1〜col5は空で送信）")
        # 添付
        self._clear_common_attach()
        self._clear_indiv_folder()
        # 受信者検索
        self._recipient_search.clear()
        # ジョブ名・進捗
        self._job_name.clear()
        self._progress.setVisible(False)
        self._progress_label.setText("")

    def _on_mode_change(self):
        is_pos = self._rb_by_pos.isChecked()
        self._pos_panel.setVisible(is_pos)
        self._attend_panel.setVisible(not is_pos)
        if not is_pos:
            self._load_meeting_combo()
        self._clear_recipient_checks()

    def _load_meeting_combo(self):
        from app.services.meeting_service import get_meetings
        session = get_session()
        try:
            self._meeting_combo.blockSignals(True)
            self._meeting_combo.clear()
            self._meeting_combo.addItem("（会議を選択）", None)
            for m in get_meetings(session):
                scope = "全員" if not m.target_position_ids else "役職指定"
                self._meeting_combo.addItem(
                    f"{m.date.strftime('%Y/%m/%d')}　{m.name}　（{scope}）", m.id)
            self._meeting_combo.blockSignals(False)
        finally:
            session.close()

    def _on_pos_select(self):
        selected_pos_ids = {
            item.data(Qt.ItemDataRole.UserRole)
            for item in self._pos_list.selectedItems()
        }
        if not selected_pos_ids:
            self._clear_recipient_checks()
            return
        member_ids = {m.id for m in self._members if m.position_id in selected_pos_ids}
        self._set_recipient_checks(member_ids)

    def _on_attend_filter(self):
        meeting_id = self._meeting_combo.currentData()
        statuses = [s for s, cb in self._status_checks.items() if cb.isChecked()]
        if not meeting_id or not statuses:
            self._clear_recipient_checks()
            return
        from app.services.meeting_service import get_member_ids_by_status
        session = get_session()
        try:
            member_ids = get_member_ids_by_status(session, meeting_id, statuses)
        finally:
            session.close()
        self._set_recipient_checks(member_ids)

    def _filter_recipient_table(self):
        raw = self._recipient_search.text().strip()
        if not raw:
            for row in range(self._recipient_table.rowCount()):
                self._recipient_table.setRowHidden(row, False)
            return
        keyword = _to_katakana(raw).lower()
        for row in range(self._recipient_table.rowCount()):
            match = False
            # 通常列：会員番号(1), 事業所名(3), 氏名(5)
            for col in (1, 3, 5):
                item = self._recipient_table.item(row, col)
                if item and keyword in item.text().lower():
                    match = True
                    break
            # フリガナ隠し列：事業所名(7), 氏名(8)
            if not match:
                for col in (7, 8):
                    item = self._recipient_table.item(row, col)
                    if item and keyword in item.text().lower():
                        match = True
                        break
            self._recipient_table.setRowHidden(row, not match)

    def _set_recipient_checks(self, member_ids: set):
        self._recipient_table.setUpdatesEnabled(False)
        for row in range(self._recipient_table.rowCount()):
            item = self._recipient_table.item(row, 3)
            mid = item.data(Qt.ItemDataRole.UserRole) if item else None
            cb = self._recipient_table.cellWidget(row, 0)
            if cb and mid is not None:
                cb.blockSignals(True)
                cb.setChecked(mid in member_ids)
                cb.blockSignals(False)
        self._recipient_table.setUpdatesEnabled(True)
        self._update_recipient_count()

    def _clear_recipient_checks(self):
        self._recipient_table.setUpdatesEnabled(False)
        for row in range(self._recipient_table.rowCount()):
            cb = self._recipient_table.cellWidget(row, 0)
            if cb:
                cb.blockSignals(True)
                cb.setChecked(False)
                cb.blockSignals(False)
        self._recipient_table.setUpdatesEnabled(True)
        self._update_recipient_count()

    def _update_recipient_count(self):
        checked = 0
        no_email = 0
        for row in range(self._recipient_table.rowCount()):
            cb = self._recipient_table.cellWidget(row, 0)
            if cb and cb.isChecked():
                checked += 1
                item = self._recipient_table.item(row, 6)
                if item and item.text() == _NO_EMAIL_TEXT:
                    no_email += 1
        self._recipient_count_label.setText(f"{checked}件選択")
        if no_email:
            self._no_email_label.setText(
                f"⚠ メール無し {no_email}件が含まれています（送信時スキップ）")
        else:
            self._no_email_label.setText("")

    # ──────────────────────────────────────────────────────
    # 宛先取得
    # ──────────────────────────────────────────────────────

    def _get_selected_members(self) -> list:
        member_cache = {m.id: m for m in self._members}
        seen_ids: set = set()
        result = []
        for row in range(self._recipient_table.rowCount()):
            cb = self._recipient_table.cellWidget(row, 0)
            if not (cb and cb.isChecked()):
                continue
            item = self._recipient_table.item(row, 3)
            mid = item.data(Qt.ItemDataRole.UserRole) if item else None
            if mid and mid not in seen_ids:
                m = member_cache.get(mid)
                if m:
                    result.append(m)
                    seen_ids.add(mid)
        return result

    # ──────────────────────────────────────────────────────
    # テンプレート・署名
    # ──────────────────────────────────────────────────────

    def _on_template_select(self):
        tmpl_id = self._template_combo.currentData()
        if not tmpl_id:
            self._subject_edit.clear()
            self._body_edit.clear()
            return
        session = get_session()
        try:
            t = get_template(session, tmpl_id)
            if t:
                self._subject_edit.setText(t.subject)
                self._body_edit.setPlainText(t.body)
                if t.signature_id:
                    for i in range(self._sig_combo.count()):
                        if self._sig_combo.itemData(i) == t.signature_id:
                            self._sig_combo.setCurrentIndex(i)
                            break
        finally:
            session.close()

    # ──────────────────────────────────────────────────────
    # 差し込み・添付
    # ──────────────────────────────────────────────────────

    def _import_merge(self):
        from app.ui.dialogs.merge_preview_dialog import MergePreviewDialog
        dlg = MergePreviewDialog(
            parent=self,
            subject=self._subject_edit.text(),
            body=self._body_edit.toPlainText(),
        )
        if dlg.exec():
            self._merge_data = dlg.get_merge_data()
            self._col_labels = dlg.get_col_labels()
            label_hint = "、".join(
                f"{k}={v}" for k, v in self._col_labels.items()
            )
            status = f"{len(self._merge_data)} 件読み込み済み"
            if label_hint:
                status += f"（{label_hint}）"
            self._merge_status.setText(status)
        else:
            self._merge_data = {}
            self._col_labels = {}
            self._merge_status.setText("（差し込みなし — col1〜col5は空で送信）")

    def _select_common_attach(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "添付ファイルを選択", "")
        if paths:
            self._common_attachments = paths
            self._common_label.setText(
                ", ".join(os.path.basename(p) for p in paths))

    def _clear_common_attach(self):
        self._common_attachments = []
        self._common_label.setText("（未選択）")

    def _select_indiv_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "フォルダを選択")
        if folder:
            self._individual_folder = folder
            self._folder_label.setText(folder)
            self._attach_list = []
            self._match_label.setText("フォルダを選択しました。「添付ファイルを確認・設定」を押してください。")
            self._btn_show_attach.setVisible(False)

    def _clear_indiv_folder(self):
        self._individual_folder = ""
        self._folder_label.setText("（未選択）")
        self._attach_list = []
        self._match_label.setText("")
        self._btn_show_attach.setVisible(False)

    def _check_matching(self):
        if not self._individual_folder:
            QMessageBox.warning(self, "エラー", "フォルダを先に選択してください。")
            return
        members = self._get_selected_members()
        if not members:
            QMessageBox.warning(self, "エラー", "宛先を先に選択してください。")
            return
        rule = self._rule_edit.text().strip()
        attach_list = []
        for m in members:
            to_addr = m.email_addresses[0].address if m.email_addresses else ""
            fname = rule.replace("{会員番号}", m.member_number)
            fpath = os.path.join(self._individual_folder, fname)
            attach_list.append({
                "member_number": m.member_number,
                "org_name":      m.organization_name,
                "to_address":    to_addr,
                "filepath":      fpath,
                "found":         os.path.exists(fpath),
            })
        from app.ui.dialogs.attach_confirm_dialog import AttachConfirmDialog
        dlg = AttachConfirmDialog(attach_list, parent=self)
        if dlg.exec():
            self._attach_list = attach_list
            found = sum(1 for r in self._attach_list if r["found"])
            missing = len(self._attach_list) - found
            status = f"設定済み: {found}/{len(self._attach_list)} 件"
            if missing:
                status += f"（{missing}件はファイルなし→添付スキップ）"
            self._match_label.setText(status)
            self._btn_show_attach.setVisible(True)
        else:
            self._attach_list = []
            self._match_label.setText("（添付設定をクリアしました）")
            self._btn_show_attach.setVisible(False)

    def _show_attach_list(self):
        if not self._attach_list:
            return
        from app.ui.dialogs.attach_confirm_dialog import AttachConfirmDialog
        AttachConfirmDialog(self._attach_list, parent=self).exec()

    # ──────────────────────────────────────────────────────
    # 送信
    # ──────────────────────────────────────────────────────

    def _build_targets(self) -> list[dict]:
        subject_tpl = self._subject_edit.text()
        body_tpl = self._body_edit.toPlainText()

        sig_id = self._sig_combo.currentData()
        sig_body = ""
        if sig_id:
            sig = next((s for s in self._signatures if s.id == sig_id), None)
            if sig:
                sig_body = "\n\n" + sig.body

        attach_map: dict[str, list[str]] = {}
        for r in self._attach_list:
            if r["found"]:
                attach_map[r["member_number"]] = [r["filepath"]]

        member_cache = {m.id: m for m in self._members}

        targets = []
        for row in range(self._recipient_table.rowCount()):
            cb = self._recipient_table.cellWidget(row, 0)
            if not (cb and cb.isChecked()):
                continue
            item = self._recipient_table.item(row, 3)
            mid = item.data(Qt.ItemDataRole.UserRole) if item else None
            addr_item = self._recipient_table.item(row, 6)
            to_addr = addr_item.text() if addr_item else ""
            if to_addr == _NO_EMAIL_TEXT:
                to_addr = ""
            m = member_cache.get(mid) if mid else None
            if not m:
                continue
            merge = self._merge_data.get(m.member_number, {})
            context = {
                "事業所名":     m.organization_name,
                "役職名":       m.title or "",
                "氏名":         m.name,
                "会議所役職名": m.position.name if m.position else "",
                **{k: merge.get(k, "") for k in ["col1", "col2", "col3", "col4", "col5"]},
            }
            # ラベルエイリアス（例: {参加費} → col1 の値）
            for col_key, label in self._col_labels.items():
                context[label] = context.get(col_key, "")
            targets.append({
                "member_id":   m.id,
                "org_name":    m.organization_name,
                "to_address":  to_addr,
                "subject":     render_body(subject_tpl, context),
                "body":        render_body(body_tpl + sig_body, context),
                "attachments": list(self._common_attachments) + attach_map.get(m.member_number, []),
            })
        return targets

    def _show_send_preview(self):
        targets = self._build_targets()
        if not targets:
            QMessageBox.warning(self, "宛先未選択", "宛先を1件以上選択してください。")
            return
        from app.ui.dialogs.send_preview_dialog import SendPreviewDialog
        dlg = SendPreviewDialog(targets, parent=self)
        dlg.exec()

    def _test_send(self):
        targets = self._build_targets()
        if not targets:
            QMessageBox.warning(self, "宛先未選択",
                                "テスト送信には差し込み内容を確認するための宛先を1件以上選択してください。\n"
                                "※ 実際には選択した宛先には送信されません。")
            return
        graph_config = get_graph_config()
        if not graph_config.get("test_address"):
            QMessageBox.warning(self, "エラー",
                                "設定タブでテスト送信先アドレスを設定してください。")
            return
        t = targets[0]
        try:
            send_test_mail(graph_config, t["subject"], t["body"],
                           t.get("attachments", []))
            QMessageBox.information(
                self, "テスト送信完了",
                f"テストメールを送信しました。\n"
                f"送信先: {graph_config['test_address']}（設定タブのテスト送信先）\n\n"
                f"※ 選択した宛先（{t['org_name']}）の差し込み内容で送信しています。")
        except Exception as e:
            QMessageBox.critical(self, "エラー", str(e))

    def _execute_send(self):
        targets = self._build_targets()
        if not targets:
            QMessageBox.warning(self, "エラー", "宛先を選択してください。")
            return
        job_name = self._job_name.text().strip()
        if not job_name:
            QMessageBox.warning(self, "エラー", "ジョブ名を入力してください。")
            return
        graph_config = get_graph_config()
        if not graph_config.get("tenant_id"):
            QMessageBox.warning(self, "エラー",
                                "設定タブでMicrosoft 365設定を行ってください。")
            return

        tmpl_name = self._template_combo.currentText()
        has_attach = any(t["attachments"] for t in targets)
        no_email_count = sum(1 for t in targets if not t["to_address"])
        msg = (
            f"以下の内容で送信します。よろしいですか？\n\n"
            f"　ジョブ名　　: {job_name}\n"
            f"　操作者　　　: {self._staff_name}\n"
            f"　テンプレート: {tmpl_name}\n"
            f"　送信件数　　: {len(targets)} 件"
            + (f"（メール無し {no_email_count} 件はスキップ）" if no_email_count else "") + "\n"
            f"　添付ファイル: {'あり' if has_attach else 'なし'}\n\n"
            "送信後は取り消せません。"
        )
        ret = QMessageBox.question(
            self, "送信確認", msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if ret != QMessageBox.StandardButton.Yes:
            return

        session = get_session()
        staff = get_staff_by_name(session, self._staff_name)
        staff_id = staff.id if staff else None
        job = create_job(session, job_name, self._template_combo.currentData(), staff_id)
        start_job(session, job.id)

        self._progress.setVisible(True)
        self._progress.setMaximum(len(targets))
        self._progress.setValue(0)

        self._worker = _SendWorker(targets, graph_config, job.id, session)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(
            lambda s, e, sk: self._on_finished(job.id, s, e, sk, session))
        self._worker.start()

    def _on_progress(self, current: int, total: int, message: str):
        self._progress.setValue(current)
        self._progress_label.setText(f"[{current}/{total}] {message}")

    def _on_finished(self, job_id: int, success: int, error: int, skip: int, session):
        finish_job(session, job_id)
        session.close()
        self._progress.setVisible(False)
        QMessageBox.information(
            self, "送信完了",
            f"送信完了\n\n成功: {success} 件\nエラー: {error} 件\nスキップ: {skip} 件\n\n"
            "「送信履歴」タブで詳細を確認できます。"
        )
