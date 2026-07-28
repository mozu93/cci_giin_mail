import os
import glob
import time
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QScrollArea,
    QGroupBox, QFormLayout, QComboBox, QLabel,
    QPushButton, QCheckBox, QLineEdit, QTextEdit,
    QProgressBar, QFileDialog, QMessageBox, QInputDialog,
    QRadioButton, QButtonGroup,
    QSplitter,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from app.database.connection import get_session
from app.services.member_service import get_members
from app.services.template_service import (
    get_templates, get_template, create_template, update_template
)
from app.services.signature_service import get_signatures, get_default_signature
from app.services.position_service import get_positions
from app.services.committee_service import get_committees
from app.services.staff_service import get_staff_by_name
from app.services.email_service import (
    compile_send_targets, send_mail, send_test_mail, get_access_token,
    total_attachment_size, ATTACHMENT_SIZE_LIMIT_BYTES,
    apply_test_mode, parse_recipient_addresses,
)
from app.services.send_job_service import create_job, start_job, finish_job, add_log
from app.utils.app_config import get_config, save_config, get_graph_config
from app.ui.recipient_panel import RecipientPanel
from app.utils.validators import is_valid_email


_BASE_PLACEHOLDERS = ["{事業所名}", "{役職名}", "{氏名}", "{会議所役職名}"]
_MERGE_PLACEHOLDERS = ["{col1}", "{col2}", "{col3}", "{col4}", "{col5}"]


class _NoWheelComboBox(QComboBox):
    def wheelEvent(self, event):
        event.ignore()


def _dev_tools_enabled() -> bool:
    return os.environ.get("CCI_MAIL_DEV_TOOLS") == "1"


_SEND_INTERVAL_SECONDS = 2.0


def _split_oversized_targets(targets: list[dict]) -> tuple[list[dict], list[dict]]:
    """添付合計サイズが上限を超えるターゲットを分離する。
    戻り値: (上限内のターゲット, 上限超過のターゲット)
    """
    ok, oversized = [], []
    for t in targets:
        if total_attachment_size(t.get("attachments", [])) > ATTACHMENT_SIZE_LIMIT_BYTES:
            oversized.append(t)
        else:
            ok.append(t)
    return ok, oversized


def _duplicate_recipient_groups(targets: list[dict]) -> list[list[dict]]:
    """同じメールアドレスへ複数回送信されるターゲットを返す。"""
    grouped: dict[str, list[dict]] = {}
    for target in targets:
        address = target.get("to_address", "").strip()
        if address:
            grouped.setdefault(address.casefold(), []).append(target)
    return [items for items in grouped.values() if len(items) > 1]


_CONSECUTIVE_ERROR_LIMIT = 5


def _log_skipped_remaining(session, job_id, targets, start_index) -> int:
    """targets[start_index:] を送信ログにskipとして記録する。戻り値: 記録した件数"""
    for t in targets[start_index:]:
        add_log(session, job_id, t.get("member_id"), t.get("to_address", ""),
                t.get("subject", ""), "skip")
    return len(targets) - start_index


class _SendWorker(QThread):
    progress = pyqtSignal(int, int, str)
    finished = pyqtSignal(int, int, int)

    def __init__(self, targets: list[dict], graph_config: dict, job_id: int,
                access_token: str):
        super().__init__()
        self._targets = targets
        self._graph_config = graph_config
        self._job_id = job_id
        self._access_token = access_token
        self._cancelled = False

    def request_cancel(self):
        self._cancelled = True

    def run(self):
        session = get_session()
        try:
            success = error = skip = 0
            consecutive_errors = 0
            total = len(self._targets)
            for i, t in enumerate(self._targets, 1):
                if self._cancelled:
                    remaining = _log_skipped_remaining(
                        session, self._job_id, self._targets, i - 1)
                    skip += remaining
                    self.progress.emit(
                        total, total, f"中止しました（残り{remaining}件は未送信）")
                    break
                to_addr = t["to_address"]
                if not to_addr:
                    add_log(session, self._job_id, t.get("member_id"),
                            "", t["subject"], "skip")
                    skip += 1
                    self.progress.emit(i, total, f"スキップ: {t['org_name']}")
                    continue
                try:
                    mail_options = {"access_token": self._access_token}
                    if t.get("cc_addresses"):
                        mail_options["cc_addresses"] = t["cc_addresses"]
                    if t.get("bcc_addresses"):
                        mail_options["bcc_addresses"] = t["bcc_addresses"]
                    send_mail(self._graph_config, to_addr, t["subject"],
                              t["body"], t.get("attachments", []),
                              **mail_options)
                    add_log(session, self._job_id, t.get("member_id"),
                            to_addr, t["subject"], "success")
                    success += 1
                    consecutive_errors = 0
                    self.progress.emit(i, total, f"送信済: {t['org_name']}")
                except Exception as e:
                    add_log(session, self._job_id, t.get("member_id"),
                            to_addr, t["subject"], "error", str(e))
                    error += 1
                    consecutive_errors += 1
                    self.progress.emit(i, total, f"エラー: {t['org_name']} — {e}")
                    if consecutive_errors >= _CONSECUTIVE_ERROR_LIMIT:
                        remaining = _log_skipped_remaining(
                            session, self._job_id, self._targets, i)
                        skip += remaining
                        self.progress.emit(
                            total, total,
                            f"エラーが{_CONSECUTIVE_ERROR_LIMIT}件連続したため中断しました"
                            f"（残り{remaining}件は未送信）")
                        break
                if i < total and not self._cancelled:
                    time.sleep(_SEND_INTERVAL_SECONDS)
            self.finished.emit(success, error, skip)
        finally:
            session.close()


class SendTab(QWidget):
    def __init__(self, staff_name: str = ""):
        super().__init__()
        self._staff_name = staff_name
        self._merge_data: dict[str, dict] = {}
        self._col_labels: dict[str, str] = {}
        self._common_attachments: list[str] = []
        self._individual_folder: str = ""
        self._attach_list: list[dict] = []
        self._members: list = []
        self._signatures: list = []
        self._build()

    # ──────────────────────────────────────────────────────
    # UI構築
    # ──────────────────────────────────────────────────────

    def _build(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(4, 4, 4, 4)
        main_layout.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)

        self._recipient = RecipientPanel()
        splitter.addWidget(self._recipient)
        splitter.addWidget(self._build_left_column())

        splitter.setSizes([380, 380])
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)

        main_layout.addWidget(splitter)

        self._load_combos()

    def _build_left_column(self) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)

        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setSpacing(8)
        layout.setContentsMargins(4, 4, 4, 4)

        btn_clear = QPushButton("すべてクリア")
        btn_clear.clicked.connect(self._clear_all)
        layout.addWidget(btn_clear)

        sections = [self._build_step1(), self._build_step2()]
        if _dev_tools_enabled():
            sections.append(self._build_merge_section())
        sections.append(self._build_attach_section())
        sections.append(self._build_final_section())
        for i, grp in enumerate(sections, 1):
            grp.setTitle(f"Step {i}：{grp.title()}")
            layout.addWidget(grp)
        layout.addStretch()

        scroll.setWidget(inner)
        return scroll

    def _build_step1(self) -> QGroupBox:
        grp = QGroupBox("宛先条件")
        layout = QVBoxLayout(grp)

        mode_row = QHBoxLayout()
        self._rb_by_list = QRadioButton("名簿から選択")
        self._rb_by_pos = QRadioButton("役職で選ぶ")
        self._rb_by_committee = QRadioButton("委員会で選ぶ")
        self._rb_by_attend = QRadioButton("会議の出欠で選ぶ")
        bg = QButtonGroup(self)
        bg.addButton(self._rb_by_list)
        bg.addButton(self._rb_by_pos)
        bg.addButton(self._rb_by_committee)
        bg.addButton(self._rb_by_attend)
        self._rb_by_list.toggled.connect(self._on_mode_change)
        self._rb_by_pos.toggled.connect(self._on_mode_change)
        self._rb_by_committee.toggled.connect(self._on_mode_change)
        self._rb_by_attend.toggled.connect(self._on_mode_change)
        mode_row.addWidget(self._rb_by_list)
        mode_row.addWidget(self._rb_by_pos)
        mode_row.addWidget(self._rb_by_committee)
        mode_row.addWidget(self._rb_by_attend)
        mode_row.addStretch()
        layout.addLayout(mode_row)

        self._pos_panel = QWidget()
        pp = QVBoxLayout(self._pos_panel)
        pp.setContentsMargins(0, 0, 0, 0)
        pp.addWidget(QLabel("会議所役職（複数選択可）："))
        self._pos_row = QHBoxLayout()
        self._pos_checks: dict[int, QCheckBox] = {}
        pp.addLayout(self._pos_row)
        self._pos_panel.setVisible(False)
        layout.addWidget(self._pos_panel)

        self._committee_panel = QWidget()
        cp = QVBoxLayout(self._committee_panel)
        cp.setContentsMargins(0, 0, 0, 0)
        cp.addWidget(QLabel("委員会（複数選択可）："))
        self._committee_row = QHBoxLayout()
        self._committee_checks: dict[int, QCheckBox] = {}
        cp.addLayout(self._committee_row)
        self._committee_panel.setVisible(False)
        layout.addWidget(self._committee_panel)

        self._attend_panel = QWidget()
        ap = QVBoxLayout(self._attend_panel)
        ap.setContentsMargins(0, 0, 0, 0)
        mrow = QHBoxLayout()
        mrow.addWidget(QLabel("会議:"))
        self._meeting_combo = _NoWheelComboBox()
        self._meeting_combo.currentIndexChanged.connect(self._on_attend_filter)
        mrow.addWidget(self._meeting_combo, 1)
        ap.addLayout(mrow)
        self._attend_source_label = QLabel("")
        self._attend_source_label.setStyleSheet("color: #6B7280; font-size: 11px;")
        ap.addWidget(self._attend_source_label)
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

        self._rb_by_list.setChecked(True)
        return grp

    def _build_step2(self) -> QGroupBox:
        grp = QGroupBox("テンプレート・署名選択")
        outer = QVBoxLayout(grp)

        f = QFormLayout()
        self._template_combo = _NoWheelComboBox()
        self._template_combo.currentIndexChanged.connect(self._on_template_select)
        self._sig_combo = _NoWheelComboBox()
        self._subject_edit = QLineEdit()
        self._body_edit = QTextEdit()
        self._body_edit.setMinimumHeight(200)
        self._body_edit.setMaximumHeight(280)
        self._btn_expand_body = QPushButton("本文を拡大して編集")
        self._btn_expand_body.clicked.connect(self._expand_body_edit)
        f.addRow("テンプレート", self._template_combo)
        f.addRow("署名", self._sig_combo)
        f.addRow("件名", self._subject_edit)
        f.addRow("本文", self._body_edit)
        f.addRow("", self._btn_expand_body)
        outer.addLayout(f)

        ph_row = QHBoxLayout()
        placeholders = list(_BASE_PLACEHOLDERS)
        if _dev_tools_enabled():
            placeholders += _MERGE_PLACEHOLDERS
        for ph in placeholders:
            btn = QPushButton(ph)
            btn.setFlat(True)
            btn.setStyleSheet(
                "font-size: 12px; color: #1E40AF; padding: 2px 6px;"
                "border: 1px solid #BFDBFE; border-radius: 3px;")
            btn.clicked.connect(lambda checked, p=ph: self._insert_placeholder(p))
            ph_row.addWidget(btn)
        ph_row.addStretch()
        outer.addLayout(ph_row)

        btn_row2 = QHBoxLayout()
        self._btn_save_template = QPushButton("テンプレートとして保存")
        self._btn_save_template.clicked.connect(self._save_as_template)
        btn_row2.addWidget(self._btn_save_template)
        btn_row2.addStretch()
        outer.addLayout(btn_row2)
        self._step2_status_label = QLabel("")
        outer.addWidget(self._step2_status_label)

        return grp

    def _build_merge_section(self) -> QGroupBox:
        grp = QGroupBox("差し込みデータ（任意）")
        layout = QVBoxLayout(grp)
        btn = QPushButton("CSV/Excelをインポート")
        btn.clicked.connect(self._import_merge)
        self._merge_status = QLabel("（未読み込み — col1〜col5は空で送信）")
        layout.addWidget(btn)
        layout.addWidget(self._merge_status)
        return grp

    def _build_attach_section(self) -> QGroupBox:
        grp = QGroupBox("添付ファイル（任意）")
        layout = QVBoxLayout(grp)

        self._chk_use_attach = QCheckBox("添付ファイルを使用する")
        self._chk_use_attach.toggled.connect(self._on_use_attach_toggled)
        layout.addWidget(self._chk_use_attach)

        self._attach_body = QWidget()
        body_layout = QVBoxLayout(self._attach_body)
        body_layout.setContentsMargins(0, 0, 0, 0)

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
        body_layout.addLayout(common_row)

        body_layout.addWidget(QLabel(
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
        body_layout.addLayout(folder_row)

        rule_row = QHBoxLayout()
        rule_row.addWidget(QLabel("ファイル名:"))
        self._rule_edit = QLineEdit("{会員番号}_*.pdf")
        self._rule_edit.setToolTip(
            "{会員番号} の直後にアンダースコアを挟んだ命名を推奨します。\n"
            "例: A001_請求書.pdf、A001_確認書_○○商事.pdf\n"
            "* は任意の文字列にマッチします（ワイルドカード）。")
        rule_row.addWidget(self._rule_edit)
        btn_match = QPushButton("添付ファイルを確認・設定")
        btn_match.clicked.connect(self._check_matching)
        rule_row.addWidget(btn_match)
        body_layout.addLayout(rule_row)

        match_row = QHBoxLayout()
        self._match_label = QLabel("")
        match_row.addWidget(self._match_label)
        self._btn_show_attach = QPushButton("一覧を確認")
        self._btn_show_attach.setVisible(False)
        self._btn_show_attach.clicked.connect(self._show_attach_list)
        match_row.addWidget(self._btn_show_attach)
        body_layout.addLayout(match_row)

        layout.addWidget(self._attach_body)
        self._attach_body.setVisible(False)

        return grp

    def _on_use_attach_toggled(self, checked: bool):
        self._attach_body.setVisible(checked)

    def _build_final_section(self) -> QGroupBox:
        grp = QGroupBox("最終確認・送信")
        layout = QVBoxLayout(grp)

        f = QFormLayout()
        self._job_name = QLineEdit()
        self._job_name.setPlaceholderText("例：2026年6月 総会案内")
        f.addRow("ジョブ名", self._job_name)
        self._cc_edit = QLineEdit()
        self._cc_edit.setPlaceholderText("任意。複数はカンマ、セミコロン、改行で区切る")
        self._bcc_edit = QLineEdit()
        self._bcc_edit.setPlaceholderText("任意。複数はカンマ、セミコロン、改行で区切る")
        f.addRow("CC", self._cc_edit)
        f.addRow("BCC", self._bcc_edit)
        layout.addLayout(f)
        self._test_mode_label = QLabel("")
        self._test_mode_label.setWordWrap(True)
        layout.addWidget(self._test_mode_label)

        btn_row = QHBoxLayout()
        self._btn_test = QPushButton("テスト送信（1通）")
        self._btn_test.clicked.connect(self._test_send)
        btn_preview = QPushButton("差し込みプレビュー")
        btn_preview.clicked.connect(self._show_send_preview)
        self._btn_send = QPushButton("送信実行")
        self._btn_send.setStyleSheet(
            "font-weight: bold; background-color: #1E40AF; color: white;")
        self._btn_send.clicked.connect(self._execute_send)
        self._btn_cancel = QPushButton("送信を中止")
        self._btn_cancel.setStyleSheet(
            "background-color: #DC2626; color: white;")
        self._btn_cancel.setVisible(False)
        self._btn_cancel.clicked.connect(self._cancel_send)
        btn_row.addWidget(self._btn_test)
        btn_row.addWidget(btn_preview)
        btn_row.addStretch()
        btn_row.addWidget(self._btn_cancel)
        btn_row.addWidget(self._btn_send)
        layout.addLayout(btn_row)

        self._progress = QProgressBar()
        self._progress.setVisible(False)
        self._progress_label = QLabel("")
        layout.addWidget(self._progress)
        layout.addWidget(self._progress_label)
        self._update_test_button_label()
        return grp

    # ──────────────────────────────────────────────────────
    # データ読み込み
    # ──────────────────────────────────────────────────────

    def refresh(self):
        self._load_combos()
        self._update_test_button_label()

    def _update_test_button_label(self):
        graph_config = get_graph_config()
        addr = graph_config.get("test_address")
        self._btn_test.setText(f"{addr} にテスト送信" if addr else "テスト送信（未設定）")
        if graph_config.get("test_mode"):
            self._test_mode_label.setText(
                f"【テストモード】本番宛先へは送信せず、すべて {addr or '未設定'} へ送ります。")
            self._test_mode_label.setStyleSheet(
                "background: #FEF3C7; color: #92400E; padding: 6px; font-weight: bold;")
        else:
            self._test_mode_label.clear()
            self._test_mode_label.setStyleSheet("")

    def _rebuild_check_row(self, row: QHBoxLayout, checks: dict, items: list,
                          on_change) -> None:
        while row.count():
            child = row.takeAt(0)
            w = child.widget()
            if w:
                w.deleteLater()
        checks.clear()
        for obj in items:
            cb = QCheckBox(obj.name)
            cb.stateChanged.connect(on_change)
            row.addWidget(cb)
            checks[obj.id] = cb
        row.addStretch()

    def _load_combos(self):
        session = get_session()
        try:
            self._rebuild_check_row(self._pos_row, self._pos_checks,
                                    get_positions(session), self._on_pos_select)
            self._rebuild_check_row(self._committee_row, self._committee_checks,
                                    get_committees(session), self._on_committee_select)

            self._members = get_members(session)
            self._recipient.load_members(self._members)

            self._template_combo.blockSignals(True)
            self._template_combo.clear()
            self._template_combo.addItem("（選択してください）", None)
            for t in get_templates(session):
                self._template_combo.addItem(t.name, t.id)
            self._template_combo.blockSignals(False)

            staff = get_staff_by_name(session, self._staff_name) if self._staff_name else None
            staff_id = staff.id if staff else None
            self._signatures = get_signatures(session, staff_id) if staff_id else []
            self._sig_combo.clear()
            self._sig_combo.addItem("（なし）", None)
            for s in self._signatures:
                self._sig_combo.addItem(s.name, s.id)
            default_sig = get_default_signature(session, staff_id) if staff_id else None
            if default_sig:
                for i in range(self._sig_combo.count()):
                    if self._sig_combo.itemData(i) == default_sig.id:
                        self._sig_combo.setCurrentIndex(i)
                        break
        finally:
            session.close()

    # ──────────────────────────────────────────────────────
    # 宛先フィルタリング
    # ──────────────────────────────────────────────────────

    def _clear_all(self):
        self._rb_by_list.setChecked(True)
        for cb in self._pos_checks.values():
            cb.setChecked(False)
        for cb in self._committee_checks.values():
            cb.setChecked(False)
        for cb in self._status_checks.values():
            cb.setChecked(False)
        self._recipient.clear_checks()
        self._template_combo.setCurrentIndex(0)
        self._sig_combo.setCurrentIndex(0)
        self._subject_edit.clear()
        self._body_edit.clear()
        self._merge_data = {}
        self._col_labels = {}
        if hasattr(self, "_merge_status"):
            self._merge_status.setText("（未読み込み — col1〜col5は空で送信）")
        self._chk_use_attach.setChecked(False)
        self._clear_common_attach()
        self._clear_indiv_folder()
        self._recipient._search.clear()
        self._job_name.clear()
        self._cc_edit.clear()
        self._bcc_edit.clear()
        self._progress.setVisible(False)
        self._progress_label.setText("")

    def _on_mode_change(self):
        is_pos = self._rb_by_pos.isChecked()
        is_committee = self._rb_by_committee.isChecked()
        is_attend = self._rb_by_attend.isChecked()
        self._pos_panel.setVisible(is_pos)
        self._committee_panel.setVisible(is_committee)
        self._attend_panel.setVisible(is_attend)
        if is_attend:
            self._load_meeting_combo()
        self._recipient.clear_checks()

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
            pid for pid, cb in self._pos_checks.items() if cb.isChecked()
        }
        if not selected_pos_ids:
            self._recipient.clear_checks()
            return
        member_ids = {m.id for m in self._members if m.position_id in selected_pos_ids}
        self._recipient.set_checks_by_member_ids(member_ids)

    def _on_committee_select(self):
        selected_committee_ids = {
            cid for cid, cb in self._committee_checks.items() if cb.isChecked()
        }
        if not selected_committee_ids:
            self._recipient.clear_checks()
            return
        member_ids = {m.id for m in self._members
                     if m.committee_id in selected_committee_ids}
        self._recipient.set_checks_by_member_ids(member_ids)

    def _on_attend_filter(self):
        from app.services.meeting_service import get_member_ids_by_status

        meeting_id = self._meeting_combo.currentData()
        if not meeting_id:
            self._attend_source_label.setText("")
            self._recipient.clear_checks()
            return

        self._attend_source_label.setText(
            "※ 未回答は「事前登録」、出席・代理・委任・欠席は「当日受付」の結果を使用します")

        session = get_session()
        try:
            statuses = [s for s, cb in self._status_checks.items() if cb.isChecked()]
            if not statuses:
                self._recipient.clear_checks()
                return
            member_ids = get_member_ids_by_status(session, meeting_id, statuses)
        finally:
            session.close()
        self._recipient.set_checks_by_member_ids(member_ids)

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

    def _expand_body_edit(self):
        from PyQt6.QtWidgets import QDialog, QVBoxLayout as _QVBoxLayout
        dlg = QDialog(self)
        dlg.setWindowTitle("本文編集")
        dlg.resize(700, 600)
        layout = _QVBoxLayout(dlg)
        editor = QTextEdit()
        editor.setPlainText(self._body_edit.toPlainText())
        layout.addWidget(editor)
        btn_row = QHBoxLayout()
        btn_ok = QPushButton("反映して閉じる")
        btn_ok.clicked.connect(dlg.accept)
        btn_row.addStretch()
        btn_row.addWidget(btn_ok)
        layout.addLayout(btn_row)
        if dlg.exec():
            self._body_edit.setPlainText(editor.toPlainText())

    def _insert_placeholder(self, placeholder: str):
        self._body_edit.setFocus()
        self._body_edit.insertPlainText(placeholder)

    def _save_as_template(self):
        subject = self._subject_edit.text().strip()
        body = self._body_edit.toPlainText().strip()
        if not subject or not body:
            QMessageBox.warning(self, "入力エラー", "件名と本文を入力してください。")
            return
        sig_id = self._sig_combo.currentData()
        tmpl_id = self._template_combo.currentData()
        session = get_session()
        try:
            if tmpl_id:
                tmpl_name = self._template_combo.currentText()
                ret = QMessageBox.question(
                    self, "上書き確認",
                    f"テンプレート「{tmpl_name}」を上書き保存しますか？",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No)
                if ret != QMessageBox.StandardButton.Yes:
                    return
                try:
                    update_template(session, tmpl_id, subject=subject, body=body,
                                    signature_id=sig_id)
                except Exception as e:
                    QMessageBox.critical(self, "エラー", str(e))
                    return
                saved_id = tmpl_id
            else:
                name, ok = QInputDialog.getText(
                    self, "テンプレート名", "新しいテンプレート名を入力してください：")
                name = name.strip()
                if not ok or not name:
                    return
                try:
                    new_tmpl = create_template(session, name, subject, body,
                                               signature_id=sig_id)
                except Exception as e:
                    QMessageBox.critical(self, "エラー", str(e))
                    return
                saved_id = new_tmpl.id
        finally:
            session.close()

        self._load_combos()
        for i in range(self._template_combo.count()):
            if self._template_combo.itemData(i) == saved_id:
                self._template_combo.setCurrentIndex(i)
                break
        from app.ui.widgets.inline_status import show_inline_message
        show_inline_message(self._step2_status_label, "テンプレートを保存しました")

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
            label_hint = "、".join(f"{k}={v}" for k, v in self._col_labels.items())
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
        members = self._recipient.get_selected_members()
        if not members:
            QMessageBox.warning(self, "エラー", "宛先を先に選択してください。")
            return
        rule = self._rule_edit.text().strip()
        attach_list = []
        for m in members:
            to_addr = m.email_addresses[0].address if m.email_addresses else ""
            pattern = os.path.join(
                self._individual_folder,
                rule.replace("{会員番号}", glob.escape(m.member_number)))
            matched = sorted(glob.glob(pattern))
            attach_list.append({
                "member_number": m.member_number,
                "org_name":      m.organization_name,
                "to_address":    to_addr,
                "filepaths":     matched,
                "found":         len(matched) > 0,
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

        use_attach = self._chk_use_attach.isChecked()
        attach_map: dict[str, list[str]] = {
            r["member_number"]: r["filepaths"]
            for r in self._attach_list if r["found"]
        } if use_attach else {}
        common_attachments = self._common_attachments if use_attach else []
        member_cache = {m.id: m for m in self._members}
        table = self._recipient.table
        no_email_text = self._recipient.no_email_text

        checked_rows = []
        for row in range(table.rowCount()):
            cb = table.cellWidget(row, 0)
            if not (cb and cb.isChecked()):
                continue
            item = table.item(row, 3)
            mid = item.data(Qt.ItemDataRole.UserRole) if item else None
            addr_item = table.item(row, 6)
            to_addr = addr_item.text() if addr_item else ""
            if to_addr == no_email_text:
                to_addr = ""
            m = member_cache.get(mid) if mid else None
            if not m:
                continue
            checked_rows.append({"member": m, "to_address": to_addr})

        cc_addresses = parse_recipient_addresses(self._cc_edit.text())
        bcc_addresses = parse_recipient_addresses(self._bcc_edit.text())
        invalid = [
            address for address in cc_addresses + bcc_addresses
            if not is_valid_email(address)
        ]
        if invalid:
            raise ValueError(
                "CC/BCCのメールアドレス形式が正しくありません: "
                + "、".join(invalid))
        targets = compile_send_targets(
            checked_rows=checked_rows,
            subject_tpl=subject_tpl,
            body_tpl=body_tpl,
            sig_body=sig_body,
            merge_data=self._merge_data,
            col_labels=self._col_labels,
            common_attachments=common_attachments,
            attach_map=attach_map,
        )
        if isinstance(targets, list):
            for target in targets:
                target["cc_addresses"] = list(cc_addresses)
                target["bcc_addresses"] = list(bcc_addresses)
        return targets

    def _show_send_preview(self):
        try:
            targets = self._build_targets()
        except ValueError as e:
            QMessageBox.warning(self, "入力エラー", str(e))
            return
        if not targets:
            QMessageBox.warning(self, "宛先未選択", "宛先を1件以上選択してください。")
            return
        graph_config = get_graph_config()
        if graph_config.get("test_mode"):
            try:
                targets = apply_test_mode(targets, graph_config.get("test_address", ""))
            except ValueError as e:
                QMessageBox.warning(self, "設定エラー", str(e))
                return
        from app.ui.dialogs.send_preview_dialog import SendPreviewDialog
        SendPreviewDialog(targets, parent=self).exec()

    def _test_send(self):
        try:
            targets = self._build_targets()
        except ValueError as e:
            QMessageBox.warning(self, "入力エラー", str(e))
            return
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
        job_id = None
        session = get_session()
        try:
            staff = get_staff_by_name(session, self._staff_name)
            staff_id = staff.id if staff else None
            job = create_job(
                session,
                f"【テスト送信】{t['subject']}",
                self._template_combo.currentData(),
                staff_id,
            )
            start_job(session, job.id)
            job_id = job.id
        finally:
            session.close()
        try:
            send_test_mail(graph_config, t["subject"], t["body"],
                           t.get("attachments", []))
            session = get_session()
            try:
                add_log(
                    session, job_id, t.get("member_id"),
                    graph_config["test_address"], f"【テスト】{t['subject']}",
                    "success")
                finish_job(session, job_id)
            finally:
                session.close()
            QMessageBox.information(
                self, "テスト送信完了",
                f"テストメールを送信しました。\n"
                f"送信先: {graph_config['test_address']}（設定タブのテスト送信先）\n\n"
                f"※ 選択した宛先（{t['org_name']}）の差し込み内容で送信しています。")
        except Exception as e:
            if job_id is not None:
                session = get_session()
                try:
                    add_log(
                        session, job_id, t.get("member_id"),
                        graph_config.get("test_address", ""),
                        f"【テスト】{t['subject']}", "error", str(e))
                    finish_job(session, job_id)
                finally:
                    session.close()
            QMessageBox.critical(self, "エラー", str(e))

    def _execute_send(self):
        try:
            targets = self._build_targets()
        except ValueError as e:
            QMessageBox.warning(self, "入力エラー", str(e))
            return
        if not targets:
            QMessageBox.warning(self, "エラー", "宛先を選択してください。")
            return

        targets, oversized = _split_oversized_targets(targets)
        if oversized:
            names = "\n".join(f"・{t['org_name']}" for t in oversized)
            ret = QMessageBox.question(
                self, "添付サイズ超過",
                f"以下の宛先は添付ファイル合計サイズが上限（3MB）を超えています。\n"
                f"送信対象から除外して続行しますか？\n\n{names}",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No)
            if ret != QMessageBox.StandardButton.Yes:
                return
            if not targets:
                QMessageBox.warning(self, "エラー", "送信可能な宛先がありません。")
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

        duplicates = _duplicate_recipient_groups(targets)
        if duplicates:
            details = []
            for group in duplicates[:10]:
                address = group[0]["to_address"].strip()
                organizations = "、".join(t["org_name"] for t in group)
                details.append(f"・{address}: {organizations}")
            if len(duplicates) > 10:
                details.append(f"ほか {len(duplicates) - 10}件")
            QMessageBox.warning(
                self, "重複宛先",
                "同じメールアドレスが複数の送信対象に含まれています。\n"
                "誤って同じメールを複数回送らないよう、宛先を見直してください。\n\n"
                + "\n".join(details))
            return

        test_mode = bool(graph_config.get("test_mode"))
        if test_mode:
            try:
                targets = apply_test_mode(
                    targets, graph_config.get("test_address", ""))
            except ValueError as e:
                QMessageBox.warning(self, "設定エラー", str(e))
                return

        try:
            access_token, account_username = get_access_token(
                graph_config, return_account=True)
        except Exception as e:
            QMessageBox.critical(self, "認証エラー", str(e))
            return

        if account_username and graph_config.get("account_username") != account_username:
            config = get_config()
            graph = config.get("graph", {}).copy()
            graph["account_username"] = account_username
            config["graph"] = graph
            save_config(config)
            graph_config = graph

        tmpl_name = self._template_combo.currentText()
        has_attach = any(t["attachments"] for t in targets)
        no_email_count = sum(1 for t in targets if not t["to_address"])
        msg = (
            f"以下の内容で送信します。よろしいですか？\n\n"
            f"　ジョブ名　　: {job_name}\n"
            f"　操作者　　　: {self._staff_name}\n"
            f"　認証アカウント: {account_username or '取得不可'}\n"
            f"　代理差出人　: {graph_config.get('from_address') or '認証アカウント本人'}\n"
            f"　CC　　　　　: {self._cc_edit.text().strip() or 'なし'}\n"
            f"　BCC　　　　 : {self._bcc_edit.text().strip() or 'なし'}\n"
            f"　送信モード　: {'テストモード（全件をテスト送信先へ振替）' if test_mode else '通常送信'}\n"
            f"　テンプレート: {tmpl_name}\n"
            f"　送信件数　　: {len(targets)} 件"
            + (f"（メール無し {no_email_count} 件はスキップ）" if no_email_count else "") + "\n"
            f"　添付ファイル: {'あり' if has_attach else 'なし'}\n\n"
            "送信後は取り消せません。"
        )
        ret = QMessageBox.question(
            self, "送信確認", msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if ret != QMessageBox.StandardButton.Yes:
            return

        session = get_session()
        try:
            staff = get_staff_by_name(session, self._staff_name)
            staff_id = staff.id if staff else None
            job = create_job(session, job_name, self._template_combo.currentData(), staff_id)
            start_job(session, job.id)
            job_id = job.id
        finally:
            session.close()

        self._progress.setVisible(True)
        self._progress.setMaximum(len(targets))
        self._progress.setValue(0)
        self._btn_send.setEnabled(False)
        self._btn_cancel.setVisible(True)

        self._worker = _SendWorker(targets, graph_config, job_id, access_token)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(
            lambda s, e, sk: self._on_finished(job_id, s, e, sk))
        self._worker.start()

    def _cancel_send(self):
        if not hasattr(self, "_worker") or not self._worker.isRunning():
            return
        ret = QMessageBox.question(
            self, "送信中止確認",
            "送信を中止しますか？\n未送信の宛先には送信されません。\n"
            "送信済みの分は取り消せません。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if ret != QMessageBox.StandardButton.Yes:
            return
        self._worker.request_cancel()
        self._btn_cancel.setEnabled(False)

    def _on_progress(self, current: int, total: int, message: str):
        self._progress.setValue(current)
        self._progress_label.setText(f"[{current}/{total}] {message}")

    def _on_finished(self, job_id: int, success: int, error: int, skip: int):
        session = get_session()
        try:
            finish_job(session, job_id)
        finally:
            session.close()
        self._btn_send.setEnabled(True)
        self._btn_cancel.setVisible(False)
        self._btn_cancel.setEnabled(True)
        self._progress.setVisible(False)
        QMessageBox.information(
            self, "送信完了",
            f"送信完了\n\n成功: {success} 件\nエラー: {error} 件\nスキップ: {skip} 件\n\n"
            "「送信履歴」タブで詳細を確認できます。"
        )
