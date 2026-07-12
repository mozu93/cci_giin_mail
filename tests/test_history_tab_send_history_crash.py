"""送信履歴タブでジョブ選択時にDetachedInstanceErrorでクラッシュしないことの回帰テスト"""
from app.database.models import EmailTemplate, Staff, Member
from app.services.send_job_service import create_job, add_log


def test_history_tab_job_select_does_not_crash(qtbot, monkeypatch, db_sessionmaker):
    SessionLocal = db_sessionmaker

    setup_session = SessionLocal()
    tmpl = EmailTemplate(name="案内", subject="件名", body="本文")
    staff = Staff(name="田中")
    member = Member(member_number="A-001", organization_name="○○商事", name="山田太郎")
    setup_session.add_all([tmpl, staff, member])
    setup_session.flush()
    job = create_job(setup_session, "テストジョブ", tmpl.id, staff.id)
    add_log(setup_session, job.id, member.id, "a@example.com", "件名", "success")
    setup_session.commit()
    setup_session.close()

    # get_session() は呼び出しごとに新しいセッションを返し、
    # HistoryTab側は都度セッションをcloseする実運用と同じ状況を再現する
    monkeypatch.setattr("app.ui.history_tab.get_session", lambda: SessionLocal())

    from app.ui.history_tab import HistoryTab
    tab = HistoryTab()
    qtbot.addWidget(tab)

    assert tab._job_table.rowCount() == 1
    tab._job_table.selectRow(0)  # ここでセッションがcloseされたjob/staffにアクセスする

    assert tab._log_table.rowCount() == 1
    assert tab._log_table.item(0, 0).text() == "○○商事"
