"""送信履歴タブの「配信状況を更新」ボタンのUIフローを検証する。"""
from app.database.models import EmailTemplate, Staff, Member
from app.services.send_job_service import create_job, add_log


def test_refresh_delivery_status_updates_ui_and_db(qtbot, monkeypatch, db_sessionmaker):
    SessionLocal = db_sessionmaker

    setup_session = SessionLocal()
    tmpl = EmailTemplate(name="案内", subject="件名", body="本文")
    staff = Staff(name="田中")
    member = Member(member_number="A-001", organization_name="○○商事", name="山田太郎")
    setup_session.add_all([tmpl, staff, member])
    setup_session.flush()
    job = create_job(setup_session, "テストジョブ", tmpl.id, staff.id)
    log = add_log(setup_session, job.id, member.id, "yamada@example.com", "件名", "success")
    from datetime import datetime
    log.sent_at = datetime.now()
    setup_session.commit()
    log_id = log.id
    setup_session.close()

    monkeypatch.setattr("app.ui.history_tab.get_session", lambda: SessionLocal())
    monkeypatch.setattr("app.ui.history_tab.get_graph_config", lambda: {"tenant_id": "t", "client_id": "c"})

    calls = []

    def fake_get_delivery_trace(graph_config, to_address, subject, sent_at):
        calls.append((to_address, subject, sent_at))
        return {"status": "delivered", "message": "Microsoft 365で配信済みです。"}

    monkeypatch.setattr("app.services.email_service.get_delivery_trace", fake_get_delivery_trace)

    from app.ui.history_tab import HistoryTab
    tab = HistoryTab()
    qtbot.addWidget(tab)

    tab._job_table.selectRow(0)
    assert tab._log_table.rowCount() == 1

    tab._refresh_delivery_status()

    assert len(calls) == 1, f"get_delivery_trace が期待通り呼ばれること: {calls}"
    assert tab._log_table.item(0, 3).text() == "配信済み"
    assert tab._log_table.item(0, 4).text() == "Microsoft 365で配信済みです。"

    check_session = SessionLocal()
    from app.database.models import SendLog
    updated = check_session.get(SendLog, log_id)
    assert updated.delivery_status == "delivered"
    assert updated.delivery_message == "Microsoft 365で配信済みです。"
    assert updated.delivery_checked_at is not None
    check_session.close()
