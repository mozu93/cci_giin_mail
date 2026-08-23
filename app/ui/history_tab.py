import csv
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QPushButton, QLabel, QFileDialog, QMessageBox, QApplication
)
from PyQt6.QtCore import Qt
from app.database.connection import get_session
from app.services.send_job_service import (
    get_jobs, get_job_logs, update_delivery_status,
)
from app.utils.app_config import get_graph_config


class HistoryTab(QWidget):
    def __init__(self):
        super().__init__()
        self._jobs = []
        self._logs = []
        self._build()
        self._load_jobs()

    def refresh(self):
        self._load_jobs()

    def _build(self):
        layout = QVBoxLayout(self)

        # ツールバー
        toolbar = QHBoxLayout()
        btn_refresh = QPushButton("更新")
        btn_refresh.clicked.connect(self._load_jobs)
        btn_trace = QPushButton("配信状況を更新")
        btn_trace.clicked.connect(self._refresh_delivery_status)
        btn_export = QPushButton("CSV出力")
        btn_export.clicked.connect(self._export_csv)
        toolbar.addWidget(btn_refresh)
        toolbar.addWidget(btn_trace)
        toolbar.addStretch()
        toolbar.addWidget(btn_export)
        layout.addLayout(toolbar)

        splitter = QSplitter(Qt.Orientation.Vertical)

        # 上段: ジョブ一覧
        job_widget = QWidget()
        job_layout = QVBoxLayout(job_widget)
        job_layout.addWidget(QLabel(
            "送信ジョブ一覧（上段はMicrosoft 365への送信受付結果）"))
        self._job_table = QTableWidget(0, 6)
        self._job_table.setHorizontalHeaderLabels(
            ["送信日時", "操作者", "ジョブ名", "件数", "受付成功", "送信時エラー"])
        job_header = self._job_table.horizontalHeader()
        # ジョブ名が横幅を占有しすぎないよう固定し、件数・結果列へ余白を配分する。
        for column, width in ((0, 150), (1, 100), (2, 350)):
            job_header.setSectionResizeMode(column, QHeaderView.ResizeMode.Fixed)
            self._job_table.setColumnWidth(column, width)
        for column in (3, 4, 5):
            job_header.setSectionResizeMode(column, QHeaderView.ResizeMode.Stretch)
        self._job_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._job_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._job_table.selectionModel().selectionChanged.connect(self._on_job_select)
        job_layout.addWidget(self._job_table)
        splitter.addWidget(job_widget)

        # 下段: 明細
        log_widget = QWidget()
        log_layout = QVBoxLayout(log_widget)
        log_layout.addWidget(QLabel(
            "送信明細（下段は相手先への配信結果。配信失敗はここで確認できます）"))
        self._log_table = QTableWidget(0, 5)
        self._log_table.setHorizontalHeaderLabels(
            ["事業所名", "送信先アドレス", "件名", "結果", "エラー内容"])
        log_header = self._log_table.horizontalHeader()
        for column, width in ((0, 160), (1, 240), (3, 130), (4, 350)):
            log_header.setSectionResizeMode(column, QHeaderView.ResizeMode.Fixed)
            self._log_table.setColumnWidth(column, width)
        log_header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self._log_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        log_layout.addWidget(self._log_table)
        splitter.addWidget(log_widget)

        layout.addWidget(splitter)

    def _load_jobs(self):
        selected_job_id = None
        row = self._job_table.currentRow()
        if row >= 0 and self._job_table.item(row, 0):
            selected_job_id = self._job_table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        session = get_session()
        try:
            self._jobs = get_jobs(session)
        finally:
            session.close()

        self._job_table.setSortingEnabled(False)
        self._job_table.setRowCount(0)
        for j in self._jobs:
            row = self._job_table.rowCount()
            self._job_table.insertRow(row)
            sent_at = j.sent_at.strftime("%Y/%m/%d %H:%M") if j.sent_at else j.created_at.strftime("%Y/%m/%d %H:%M")
            staff_name = j.staff.name if j.staff else ""
            self._job_table.setItem(row, 0, QTableWidgetItem(sent_at))
            self._job_table.setItem(row, 1, QTableWidgetItem(staff_name))
            self._job_table.setItem(row, 2, QTableWidgetItem(j.name))
            self._job_table.setItem(row, 3, QTableWidgetItem(str(j.total_count)))
            self._job_table.setItem(row, 4, QTableWidgetItem(str(j.success_count)))
            self._job_table.setItem(row, 5, QTableWidgetItem(str(j.error_count)))
            self._job_table.item(row, 0).setData(Qt.ItemDataRole.UserRole, j.id)
        self._job_table.setSortingEnabled(True)

        self._log_table.setRowCount(0)
        if selected_job_id is not None:
            for row in range(self._job_table.rowCount()):
                item = self._job_table.item(row, 0)
                if item and item.data(Qt.ItemDataRole.UserRole) == selected_job_id:
                    self._job_table.selectRow(row)
                    break

    def _on_job_select(self):
        row = self._job_table.currentRow()
        if row < 0 or row >= len(self._jobs):
            self._log_table.setRowCount(0)
            return
        job_id = self._job_table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        session = get_session()
        try:
            self._logs = get_job_logs(session, job_id)
        finally:
            session.close()

        self._log_table.setRowCount(0)
        for log in self._logs:
            r = self._log_table.rowCount()
            self._log_table.insertRow(r)
            org_name = log.member.organization_name if log.member else ""
            self._log_table.setItem(r, 0, QTableWidgetItem(org_name))
            self._log_table.setItem(r, 1, QTableWidgetItem(log.to_address))
            self._log_table.setItem(r, 2, QTableWidgetItem(log.subject))
            delivery_label = {
                "delivered": "配信済み", "pending": "確認待ち", "failed": "配信失敗",
                "quarantined": "隔離", "filteredasspam": "スパム処理",
            }.get(log.delivery_status or "", "")
            status_label = delivery_label or {
                "success": "送信受付済み", "error": "送信エラー", "skip": "スキップ"
            }.get(log.status, log.status)
            self._log_table.setItem(r, 3, QTableWidgetItem(status_label))
            detail = log.delivery_message if delivery_label else log.error_message
            self._log_table.setItem(r, 4, QTableWidgetItem(detail or ""))

    def _refresh_delivery_status(self):
        row = self._job_table.currentRow()
        if row < 0 or row >= len(self._jobs):
            QMessageBox.information(self, "情報", "配信状況を確認するジョブを選択してください。")
            return
        if not self._logs:
            QMessageBox.information(self, "情報", "送信明細がありません。")
            return
        graph_config = get_graph_config()
        try:
            from app.services.email_service import get_delivery_trace
            session = get_session()
            checked = failed = pending = 0
            try:
                for log in self._logs:
                    if log.status != "success":
                        continue
                    QApplication.processEvents()
                    result = get_delivery_trace(
                        graph_config, log.to_address, log.subject, log.sent_at)
                    update_delivery_status(
                        session, log.id, result["status"], result.get("message", ""))
                    checked += 1
                    if result["status"] == "failed":
                        failed += 1
                    elif result["status"] == "pending":
                        pending += 1
            finally:
                session.close()
        except Exception as e:
            QMessageBox.critical(self, "配信状況の確認エラー", str(e))
            return
        self._load_jobs()
        QMessageBox.information(
            self, "配信状況を更新しました",
            f"確認: {checked} 件\n配信失敗: {failed} 件\n確認待ち: {pending} 件\n\n"
            "失敗理由は送信明細で確認できます。"
        )

    def _export_csv(self):
        row = self._job_table.currentRow()
        if row < 0:
            QMessageBox.information(self, "情報", "エクスポートするジョブを選択してください。")
            return
        if not self._logs:
            QMessageBox.information(self, "情報", "明細データがありません。")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "CSV保存", "", "CSV (*.csv)")
        if not path:
            return
        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                writer.writerow(["事業所名", "送信先アドレス", "件名", "結果",
                                 "エラー内容", "配信状況", "配信状況詳細", "送信日時"])
                for log in self._logs:
                    org_name = log.member.organization_name if log.member else ""
                    sent_at = log.sent_at.strftime("%Y/%m/%d %H:%M") if log.sent_at else ""
                    status_label = {"success": "送信受付済み", "error": "送信エラー",
                                    "skip": "スキップ"}.get(log.status, log.status)
                    writer.writerow([org_name, log.to_address, log.subject,
                                     status_label, log.error_message or "",
                                     log.delivery_status or "", log.delivery_message or "", sent_at])
            QMessageBox.information(self, "完了", f"CSVを保存しました。\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "エラー", str(e))
