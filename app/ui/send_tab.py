import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QScrollArea,
    QGroupBox, QFormLayout, QComboBox, QLabel,
    QPushButton, QCheckBox, QLineEdit, QTextEdit,
    QProgressBar, QFileDialog, QMessageBox,
    QListWidget, QListWidgetItem, QRadioButton, QButtonGroup,
    QSplitter,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from app.database.connection import get_session
from app.services.member_service import get_members
from app.services.template_service import get_templates, get_template
from app.services.signature_service import get_signatures, get_default_signature
from app.services.position_service import get_positions
from app.services.committee_service import get_committees
from app.services.staff_service import get_staff_by_name
from app.services.email_service import compile_send_targets, send_mail, send_test_mail
from app.services.send_job_service import create_job, start_job, finish_job, add_log
from app.utils.app_config import get_graph_config
from app.ui.recipient_panel import RecipientPanel


class _SendWorker(QThread):
    progress = pyqtSignal(int, int, str)
    finished = pyqtSignal(int, int, int)

    def __init__(self, targets: list[dict], graph_config: dict, job_id: int):
        super().__init__()
        self._targets = targets
        self._graph_config = graph_config
        self._job_id = job_id
        self._cancelled = False

    def request_cancel(self):
        self._cancelled = True

    def run(self):
        session = get_session()
        try:
            success = error = skip = 0
            total = len(self._targets)
            for i, t in enumerate(self._targets, 1):
                if self._cancelled:
                    remaining = total - i + 1
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
                    send_mail(self._graph_config, to_addr, t["subject"],
                              t["body"], t.get("attachments", []))
                    add_log(session, self._job_id, t.get("member_id"),
                            to_addr, t["subject"], "success")
                    success += 1
                    self.progress.emit(i, total, f"送信済: {t['org_name']}")
                except Exception as e:
                    add_log(session, self._job_id, t.get("member_id"),
                            to_addr, t["subject"], "error", str(e))
                    error += 1
                    self.progress.emit(i, total, f"エラー: {t['org_name']} — {e}")
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

        splitter.setSizes([1, 1])
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
        self._rb_by_committee = QRadioButton("委員会で選ぶ")
        self._rb_by_attend = QRadioButton("会議の出欠で選ぶ")
        self._rb_by_pos.setChecked(True)
        bg = QButtonGroup(self)
        bg.addButton(self._rb_by_pos)
        bg.addButton(self._rb_by_committee)
        bg.addButton(self._rb_by_attend)
        self._rb_by_pos.toggled.connect(self._on_mode_change)
        self._rb_by_committee.toggled.connect(self._on_mode_change)
        mode_row.addWidget(self._rb_by_pos)
        mode_row.addWidget(self._rb_by_committee)
        mode_row.addWidget(self._rb_by_attend)
        mode_row.addStretch()
        layout.addLayout(mode_row)

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

        self._committee_panel = QWidget()
        cp = QVBoxLayout(self._committee_panel)
        cp.setContentsMargins(0, 0, 0, 0)
        cp.addWidget(QLabel("委員会（複数選択可 / Ctrl+クリック）："))
        self._committee_list = QListWidget()
        self._committee_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        self._committee_list.setMaximumHeight(100)
        self._committee_list.itemSelectionChanged.connect(self._on_committee_select)
        cp.addWidget(self._committee_list)
        self._committee_panel.setVisible(False)
        layout.addWidget(self._committee_panel)

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
        self._body_edit.setMinimumHeight(200)
        self._body_edit.setMaximumHeight(280)
        self._btn_expand_body = QPushButton("本文を拡大して編集")
        self._btn_expand_body.clicked.connect(self._expand_body_edit)
        f.addRow("テンプレート", self._template_combo)
        f.addRow("署名", self._sig_combo)
        f.addRow("件名", self._subject_edit)
        f.addRow("本文", self._body_edit)
        f.addRow("", self._btn_expand_body)
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
        self._btn_send = QPushButton("送信実行")
        self._btn_send.setStyleSheet(
            "font-weight: bold; background-color: #1E40AF; color: white;")
        self._btn_send.clicked.connect(self._execute_send)
        self._btn_cancel = QPushButton("送信を中止")
        self._btn_cancel.setStyleSheet(
            "background-color: #DC2626; color: white;")
        self._btn_cancel.setVisible(False)
        self._btn_cancel.clicked.connect(self._cancel_send)
        btn_row.addWidget(btn_test)
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
        return grp

    # ──────────────────────────────────────────────────────
    # データ読み込み
    # ──────────────────────────────────────────────────────

    def refresh(self):
        self._load_combos()

    def _load_combos(self):
        session = get_session()
        try:
            self._pos_list.blockSignals(True)
            self._pos_list.clear()
            for p in get_positions(session):
                item = QListWidgetItem(p.name)
                item.setData(Qt.ItemDataRole.UserRole, p.id)
                self._pos_list.addItem(item)
            self._pos_list.blockSignals(False)

            self._committee_list.blockSignals(True)
            self._committee_list.clear()
            for c in get_committees(session):
                item = QListWidgetItem(c.name)
                item.setData(Qt.ItemDataRole.UserRole, c.id)
                self._committee_list.addItem(item)
            self._committee_list.blockSignals(False)

            self._members = get_members(session)
            self._recipient.load_members(self._members)

            self._template_combo.blockSignals(True)
            self._template_combo.clear()
            self._template_combo.addItem("（選択してください）", None)
            for t in get_templates(session):
                self._template_combo.addItem(t.name, t.id)
            self._template_combo.blockSignals(False)

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

    # ──────────────────────────────────────────────────────
    # 宛先フィルタリング
    # ──────────────────────────────────────────────────────

    def _clear_all(self):
        self._rb_by_pos.setChecked(True)
        self._pos_list.clearSelection()
        self._committee_list.clearSelection()
        for cb in self._status_checks.values():
            cb.setChecked(False)
        self._recipient.clear_checks()
        self._template_combo.setCurrentIndex(0)
        self._sig_combo.setCurrentIndex(0)
        self._subject_edit.clear()
        self._body_edit.clear()
        self._merge_data = {}
        self._col_labels = {}
        self._merge_status.setText("（未読み込み — col1〜col5は空で送信）")
        self._clear_common_attach()
        self._clear_indiv_folder()
        self._recipient._search.clear()
        self._job_name.clear()
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
            item.data(Qt.ItemDataRole.UserRole)
            for item in self._pos_list.selectedItems()
        }
        if not selected_pos_ids:
            self._recipient.clear_checks()
            return
        member_ids = {m.id for m in self._members if m.position_id in selected_pos_ids}
        self._recipient.set_checks_by_member_ids(member_ids)

    def _on_committee_select(self):
        selected_committee_ids = {
            item.data(Qt.ItemDataRole.UserRole)
            for item in self._committee_list.selectedItems()
        }
        if not selected_committee_ids:
            self._recipient.clear_checks()
            return
        member_ids = {m.id for m in self._members
                     if m.committee_id in selected_committee_ids}
        self._recipient.set_checks_by_member_ids(member_ids)

    def _on_attend_filter(self):
        meeting_id = self._meeting_combo.currentData()
        statuses = [s for s, cb in self._status_checks.items() if cb.isChecked()]
        if not meeting_id or not statuses:
            self._recipient.clear_checks()
            return
        from app.services.meeting_service import get_member_ids_by_status
        session = get_session()
        try:
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

        attach_map: dict[str, list[str]] = {
            r["member_number"]: [r["filepath"]]
            for r in self._attach_list if r["found"]
        }
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

        return compile_send_targets(
            checked_rows=checked_rows,
            subject_tpl=subject_tpl,
            body_tpl=body_tpl,
            sig_body=sig_body,
            merge_data=self._merge_data,
            col_labels=self._col_labels,
            common_attachments=self._common_attachments,
            attach_map=attach_map,
        )

    def _show_send_preview(self):
        targets = self._build_targets()
        if not targets:
            QMessageBox.warning(self, "宛先未選択", "宛先を1件以上選択してください。")
            return
        from app.ui.dialogs.send_preview_dialog import SendPreviewDialog
        SendPreviewDialog(targets, parent=self).exec()

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

        self._worker = _SendWorker(targets, graph_config, job_id)
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
