# app/ui/send_tab.py
import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QScrollArea,
    QGroupBox, QFormLayout, QComboBox, QLabel,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QPushButton, QCheckBox, QLineEdit, QTextEdit,
    QProgressBar, QFileDialog, QMessageBox, QSizePolicy,
    QListWidget, QListWidgetItem, QRadioButton, QButtonGroup
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from app.database.connection import get_session
from app.services.member_service import get_members, get_member
from app.services.template_service import get_templates, get_template
from app.services.signature_service import get_signatures, get_default_signature
from app.services.position_service import get_positions
from app.services.staff_service import get_active_staff
from app.services.email_service import render_body, send_mail, send_test_mail
from app.services.send_job_service import (
    create_job, start_job, finish_job, add_log
)
from app.utils.app_config import get_graph_config


class _SendWorker(QThread):
    progress = pyqtSignal(int, int, str)   # current, total, message
    finished = pyqtSignal(int, int, int)   # success, error, skip

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
    def __init__(self):
        super().__init__()
        self._merge_data: dict[str, dict] = {}
        self._common_attachments: list[str] = []
        self._individual_folder: str = ""
        self._attach_list: list[dict] = []
        self._build()

    def _build(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        layout = QVBoxLayout(inner)

        # Step 1: 操作者
        grp1 = QGroupBox("Step 1：操作者選択")
        f1 = QFormLayout(grp1)
        self._staff_combo = QComboBox()
        f1.addRow("操作者", self._staff_combo)
        layout.addWidget(grp1)

        # Step 2: 宛先選択
        grp2 = QGroupBox("Step 2：宛先選択")
        v2 = QVBoxLayout(grp2)

        # 選択方式切り替え
        mode_row = QHBoxLayout()
        self._rb_by_pos = QRadioButton("役職で選ぶ")
        self._rb_by_attend = QRadioButton("会議の出欠で選ぶ")
        self._rb_by_pos.setChecked(True)
        _bg = QButtonGroup(self)
        _bg.addButton(self._rb_by_pos)
        _bg.addButton(self._rb_by_attend)
        self._rb_by_pos.toggled.connect(self._on_mode_change)
        mode_row.addWidget(self._rb_by_pos)
        mode_row.addWidget(self._rb_by_attend)
        mode_row.addStretch()
        v2.addLayout(mode_row)

        # 役職パネル
        self._pos_panel = QWidget()
        _pp = QVBoxLayout(self._pos_panel)
        _pp.setContentsMargins(0, 0, 0, 0)
        _pp.addWidget(QLabel("会議所役職（複数選択可 / Ctrl+クリックで追加選択）："))
        self._pos_list = QListWidget()
        self._pos_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        self._pos_list.setMaximumHeight(90)
        self._pos_list.itemSelectionChanged.connect(self._on_pos_select)
        _pp.addWidget(self._pos_list)
        v2.addWidget(self._pos_panel)

        # 会議出欠パネル
        self._attend_panel = QWidget()
        _ap = QVBoxLayout(self._attend_panel)
        _ap.setContentsMargins(0, 0, 0, 0)
        _mrow = QHBoxLayout()
        _mrow.addWidget(QLabel("会議:"))
        self._meeting_combo = QComboBox()
        self._meeting_combo.currentIndexChanged.connect(self._on_attend_filter)
        _mrow.addWidget(self._meeting_combo, 1)
        _ap.addLayout(_mrow)
        _srow = QHBoxLayout()
        _srow.addWidget(QLabel("対象:"))
        self._status_checks: dict[str, QCheckBox] = {}
        for _s in ["未入力", "欠席", "出席", "委任", "代理"]:
            _cb = QCheckBox(_s)
            _cb.stateChanged.connect(self._on_attend_filter)
            _srow.addWidget(_cb)
            self._status_checks[_s] = _cb
        _srow.addStretch()
        _ap.addLayout(_srow)
        self._attend_panel.setVisible(False)
        v2.addWidget(self._attend_panel)

        v2.addWidget(QLabel("企業で選択："))
        self._member_table = QTableWidget(0, 3)
        self._member_table.setHorizontalHeaderLabels(["選択", "事業所名", "氏名"])
        self._member_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch)
        self._member_table.setMaximumHeight(200)
        v2.addWidget(self._member_table)
        self._selection_label = QLabel("選択中: 0 件")
        v2.addWidget(self._selection_label)
        layout.addWidget(grp2)

        # Step 3: テンプレート・署名
        grp3 = QGroupBox("Step 3：テンプレート・署名選択")
        f3 = QFormLayout(grp3)
        self._template_combo = QComboBox()
        self._template_combo.currentIndexChanged.connect(self._on_template_select)
        self._sig_combo = QComboBox()
        self._subject_edit = QLineEdit()
        self._body_edit = QTextEdit()
        self._body_edit.setMaximumHeight(150)
        f3.addRow("テンプレート", self._template_combo)
        f3.addRow("署名", self._sig_combo)
        f3.addRow("件名", self._subject_edit)
        f3.addRow("本文", self._body_edit)
        layout.addWidget(grp3)

        # Step 4: 差し込みデータ
        grp4 = QGroupBox("Step 4：差し込みデータ（任意）")
        v4 = QVBoxLayout(grp4)
        btn_merge = QPushButton("CSV/Excelをインポート")
        btn_merge.clicked.connect(self._import_merge)
        self._merge_status = QLabel("（未読み込み — col1〜col5は空で送信）")
        v4.addWidget(btn_merge)
        v4.addWidget(self._merge_status)
        layout.addWidget(grp4)

        # Step 5: 添付ファイル
        grp5 = QGroupBox("Step 5：添付ファイル（任意）")
        v5 = QVBoxLayout(grp5)

        common_row = QHBoxLayout()
        btn_common = QPushButton("全社共通ファイルを選択")
        btn_common.clicked.connect(self._select_common_attach)
        self._common_label = QLabel("（未選択）")
        common_row.addWidget(btn_common)
        common_row.addWidget(self._common_label)
        v5.addLayout(common_row)

        indiv_row = QHBoxLayout()
        btn_folder = QPushButton("会社別フォルダを選択")
        btn_folder.clicked.connect(self._select_indiv_folder)
        self._folder_label = QLabel("（未選択）")
        indiv_row.addWidget(btn_folder)
        indiv_row.addWidget(self._folder_label)
        v5.addLayout(indiv_row)

        rule_row = QHBoxLayout()
        rule_row.addWidget(QLabel("ファイル名ルール:"))
        self._rule_edit = QLineEdit("{会員番号}.pdf")
        rule_row.addWidget(self._rule_edit)
        btn_match = QPushButton("マッチング確認")
        btn_match.clicked.connect(self._check_matching)
        rule_row.addWidget(btn_match)
        v5.addLayout(rule_row)
        self._match_label = QLabel("")
        v5.addWidget(self._match_label)
        layout.addWidget(grp5)

        # Step 6: 送信
        grp6 = QGroupBox("Step 6：最終確認・送信")
        v6 = QVBoxLayout(grp6)
        self._job_name = QLineEdit()
        self._job_name.setPlaceholderText("例：2026年6月 総会案内")
        f6 = QFormLayout()
        f6.addRow("ジョブ名", self._job_name)
        v6.addLayout(f6)
        self._preview_table = QTableWidget(0, 4)
        self._preview_table.setHorizontalHeaderLabels(
            ["事業所名", "送信先アドレス", "添付", "col1"])
        self._preview_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch)
        self._preview_table.setMaximumHeight(200)
        v6.addWidget(self._preview_table)
        btn_row6 = QHBoxLayout()
        btn_preview = QPushButton("プレビュー更新")
        btn_preview.clicked.connect(self._refresh_preview)
        btn_test = QPushButton("テスト送信（1通）")
        btn_test.clicked.connect(self._test_send)
        btn_send = QPushButton("送信実行")
        btn_send.setStyleSheet("font-weight: bold; background-color: #1E40AF; color: white;")
        btn_send.clicked.connect(self._execute_send)
        btn_row6.addWidget(btn_preview)
        btn_row6.addWidget(btn_test)
        btn_row6.addStretch()
        btn_row6.addWidget(btn_send)
        v6.addLayout(btn_row6)
        self._progress = QProgressBar()
        self._progress.setVisible(False)
        self._progress_label = QLabel("")
        v6.addWidget(self._progress)
        v6.addWidget(self._progress_label)
        layout.addWidget(grp6)

        scroll.setWidget(inner)
        main_layout = QVBoxLayout(self)
        main_layout.addWidget(scroll)
        self._load_combos()

    def _load_combos(self):
        session = get_session()
        try:
            # 職員
            staff_list = get_active_staff(session)
            self._staff_combo.clear()
            self._staff_combo.addItem("（選択してください）", None)
            for s in staff_list:
                self._staff_combo.addItem(s.name, s.id)

            # 会議所役職リスト
            self._pos_list.blockSignals(True)
            self._pos_list.clear()
            positions = get_positions(session)
            for p in positions:
                item = QListWidgetItem(p.name)
                item.setData(Qt.ItemDataRole.UserRole, p.id)
                self._pos_list.addItem(item)
            self._pos_list.blockSignals(False)

            # 会員テーブル
            members = get_members(session)
            self._members = members
            self._member_table.setRowCount(0)
            for m in members:
                row = self._member_table.rowCount()
                self._member_table.insertRow(row)
                cb = QCheckBox()
                cb.stateChanged.connect(self._on_member_check)
                self._member_table.setCellWidget(row, 0, cb)
                self._member_table.setItem(row, 1, QTableWidgetItem(m.organization_name))
                self._member_table.setItem(row, 2, QTableWidgetItem(m.name))
                self._member_table.item(row, 1).setData(Qt.ItemDataRole.UserRole, m.id)

            # テンプレート
            templates = get_templates(session)
            self._templates = templates
            self._template_combo.clear()
            self._template_combo.addItem("（選択してください）", None)
            for t in templates:
                self._template_combo.addItem(t.name, t.id)

            # 署名
            signatures = get_signatures(session)
            self._signatures = signatures
            self._sig_combo.clear()
            self._sig_combo.addItem("（なし）", None)
            for s in signatures:
                self._sig_combo.addItem(s.name, s.id)
            default_sig = get_default_signature(session)
            if default_sig:
                for i in range(self._sig_combo.count()):
                    if self._sig_combo.itemData(i) == default_sig.id:
                        self._sig_combo.setCurrentIndex(i)
                        break
        finally:
            session.close()

    def _on_mode_change(self):
        is_pos = self._rb_by_pos.isChecked()
        self._pos_panel.setVisible(is_pos)
        self._attend_panel.setVisible(not is_pos)
        if not is_pos:
            self._load_meeting_combo()
        self._clear_member_checks()

    def _load_meeting_combo(self):
        from app.services.meeting_service import get_meetings
        session = get_session()
        try:
            meetings = get_meetings(session)
            self._meeting_combo.blockSignals(True)
            self._meeting_combo.clear()
            self._meeting_combo.addItem("（会議を選択）", None)
            for m in meetings:
                scope = "全員" if not m.target_position_ids else "役職指定"
                self._meeting_combo.addItem(
                    f"{m.date.strftime('%Y/%m/%d')}　{m.name}　（{scope}）", m.id)
            self._meeting_combo.blockSignals(False)
        finally:
            session.close()

    def _on_attend_filter(self):
        meeting_id = self._meeting_combo.currentData()
        statuses = [s for s, cb in self._status_checks.items() if cb.isChecked()]
        if not meeting_id or not statuses:
            self._clear_member_checks()
            return
        from app.services.meeting_service import get_member_ids_by_status
        session = get_session()
        try:
            member_ids = get_member_ids_by_status(session, meeting_id, statuses)
        finally:
            session.close()
        self._member_table.setUpdatesEnabled(False)
        for row in range(self._member_table.rowCount()):
            item = self._member_table.item(row, 1)
            mid = item.data(Qt.ItemDataRole.UserRole) if item else None
            cb = self._member_table.cellWidget(row, 0)
            if cb and mid is not None:
                cb.blockSignals(True)
                cb.setChecked(mid in member_ids)
                cb.blockSignals(False)
        self._member_table.setUpdatesEnabled(True)
        self._update_selection_label()

    def _clear_member_checks(self):
        self._member_table.setUpdatesEnabled(False)
        for row in range(self._member_table.rowCount()):
            cb = self._member_table.cellWidget(row, 0)
            if cb:
                cb.blockSignals(True)
                cb.setChecked(False)
                cb.blockSignals(False)
        self._member_table.setUpdatesEnabled(True)
        self._update_selection_label()

    def _on_pos_select(self):
        selected_pos_ids = {
            item.data(Qt.ItemDataRole.UserRole)
            for item in self._pos_list.selectedItems()
        }
        for row in range(self._member_table.rowCount()):
            item = self._member_table.item(row, 1)
            mid = item.data(Qt.ItemDataRole.UserRole) if item else None
            if mid is None:
                continue
            m = next((x for x in self._members if x.id == mid), None)
            cb = self._member_table.cellWidget(row, 0)
            if cb and m:
                cb.blockSignals(True)
                cb.setChecked(m.position_id in selected_pos_ids)
                cb.blockSignals(False)
        self._update_selection_label()

    def _on_member_check(self):
        self._update_selection_label()

    def _update_selection_label(self):
        count = sum(
            1 for row in range(self._member_table.rowCount())
            if (cb := self._member_table.cellWidget(row, 0)) and cb.isChecked()
        )
        self._selection_label.setText(f"選択中: {count} 件")

    def _get_selected_members(self) -> list:
        session = get_session()
        try:
            result = []
            seen = set()
            for row in range(self._member_table.rowCount()):
                cb = self._member_table.cellWidget(row, 0)
                if not (cb and cb.isChecked()):
                    continue
                item = self._member_table.item(row, 1)
                mid = item.data(Qt.ItemDataRole.UserRole) if item else None
                if mid and mid not in seen:
                    seen.add(mid)
                    m = get_member(session, mid)
                    if m:
                        result.append(m)
            return result
        finally:
            session.close()

    def _on_template_select(self):
        tmpl_id = self._template_combo.currentData()
        if not tmpl_id:
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

    def _import_merge(self):
        from app.ui.dialogs.merge_preview_dialog import MergePreviewDialog
        dlg = MergePreviewDialog(parent=self)
        if dlg.exec():
            self._merge_data = dlg.get_merge_data()
            self._merge_status.setText(
                f"{len(self._merge_data)} 件の差し込みデータを読み込み済み")
        else:
            self._merge_data = {}
            self._merge_status.setText("（差し込みなし — col1〜col5は空で送信）")

    def _select_common_attach(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "添付ファイルを選択", "")
        if paths:
            self._common_attachments = paths
            names = ", ".join(os.path.basename(p) for p in paths)
            self._common_label.setText(names)

    def _select_indiv_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "フォルダを選択")
        if folder:
            self._individual_folder = folder
            self._folder_label.setText(folder)

    def _check_matching(self):
        if not self._individual_folder:
            QMessageBox.warning(self, "エラー", "フォルダを先に選択してください。")
            return
        rule = self._rule_edit.text().strip()
        members = self._get_selected_members()
        if not members:
            QMessageBox.warning(self, "エラー", "宛先を先に選択してください。")
            return
        self._attach_list = []
        for m in members:
            to_addr = m.email_addresses[0].address if m.email_addresses else ""
            fname = rule.replace("{会員番号}", m.member_number)
            fpath = os.path.join(self._individual_folder, fname)
            self._attach_list.append({
                "member_number": m.member_number,
                "org_name":      m.organization_name,
                "to_address":    to_addr,
                "filepath":      fpath,
                "found":         os.path.exists(fpath),
            })
        found = sum(1 for r in self._attach_list if r["found"])
        missing = len(self._attach_list) - found
        self._match_label.setText(
            f"マッチング: {found}/{len(self._attach_list)} 件。未発見: {missing} 件")
        if missing > 0:
            from app.ui.dialogs.attach_confirm_dialog import AttachConfirmDialog
            dlg = AttachConfirmDialog(self._attach_list, parent=self)
            dlg.exec()

    def _build_targets(self) -> list[dict]:
        members = self._get_selected_members()
        subject_tpl = self._subject_edit.text()
        body_tpl = self._body_edit.toPlainText()

        # 署名
        sig_id = self._sig_combo.currentData()
        sig_body = ""
        if sig_id:
            sig = next((s for s in self._signatures if s.id == sig_id), None)
            if sig:
                sig_body = "\n\n" + sig.body

        attach_map: dict[str, list[str]] = {}
        if self._attach_list:
            for r in self._attach_list:
                if r["found"]:
                    attach_map[r["member_number"]] = [r["filepath"]]

        targets = []
        for m in members:
            to_addr = m.email_addresses[0].address if m.email_addresses else ""
            merge = self._merge_data.get(m.member_number, {})
            context = {
                "事業所名":     m.organization_name,
                "役職名":       m.title or "",
                "氏名":         m.name,
                "会議所役職名": m.position.name if m.position else "",
                **{k: merge.get(k, "") for k in ["col1","col2","col3","col4","col5"]},
            }
            subject = render_body(subject_tpl, context)
            body = render_body(body_tpl + sig_body, context)
            attachments = list(self._common_attachments)
            attachments.extend(attach_map.get(m.member_number, []))
            targets.append({
                "member_id":  m.id,
                "org_name":   m.organization_name,
                "to_address": to_addr,
                "subject":    subject,
                "body":       body,
                "attachments": attachments,
            })
        return targets

    def _refresh_preview(self):
        targets = self._build_targets()
        self._preview_table.setRowCount(0)
        for t in targets:
            row = self._preview_table.rowCount()
            self._preview_table.insertRow(row)
            self._preview_table.setItem(row, 0, QTableWidgetItem(t["org_name"]))
            self._preview_table.setItem(row, 1, QTableWidgetItem(t["to_address"]))
            has_attach = "あり" if t["attachments"] else ""
            self._preview_table.setItem(row, 2, QTableWidgetItem(has_attach))
            col1 = t["body"][:30] if t["body"] else ""
            self._preview_table.setItem(row, 3, QTableWidgetItem(col1))

    def _test_send(self):
        targets = self._build_targets()
        if not targets:
            QMessageBox.warning(self, "エラー", "宛先を選択してください。")
            return
        graph_config = get_graph_config()
        if not graph_config.get("test_address"):
            QMessageBox.warning(self, "エラー",
                                "設定タブでテスト送信先アドレスを設定してください。")
            return
        t = targets[0]
        try:
            send_test_mail(graph_config, t["subject"], t["body"])
            QMessageBox.information(self, "完了",
                                    f"テストメールを送信しました。\n宛先: {graph_config['test_address']}")
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
        staff_id = self._staff_combo.currentData()
        if not staff_id:
            QMessageBox.warning(self, "エラー", "操作者を選択してください。")
            return
        graph_config = get_graph_config()
        if not graph_config.get("tenant_id"):
            QMessageBox.warning(self, "エラー",
                                "設定タブでMicrosoft 365設定を行ってください。")
            return

        ret = QMessageBox.question(
            self, "送信確認",
            f"{len(targets)} 件に送信します。よろしいですか？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if ret != QMessageBox.StandardButton.Yes:
            return

        session = get_session()
        tmpl_id = self._template_combo.currentData()
        job = create_job(session, job_name, tmpl_id, staff_id)
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
