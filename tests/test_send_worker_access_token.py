from app.ui.send_tab import _SendWorker


class _FakeSession:
    def close(self):
        pass


def test_send_mail_receives_worker_access_token(monkeypatch):
    received = {}

    def fake_send_mail(graph_config, to_addr, subject, body, attachments,
                       access_token=None):
        received["access_token"] = access_token

    def fake_add_log(session, job_id, member_id, to_addr, subject, status, error=None):
        pass

    monkeypatch.setattr("app.ui.send_tab.send_mail", fake_send_mail)
    monkeypatch.setattr("app.ui.send_tab.add_log", fake_add_log)
    monkeypatch.setattr("app.ui.send_tab.get_session", lambda: _FakeSession())
    monkeypatch.setattr("app.ui.send_tab.time.sleep", lambda s: None)

    targets = [{"to_address": "a@example.com", "subject": "s", "body": "b",
                "org_name": "org", "member_id": 1, "attachments": []}]
    worker = _SendWorker(targets, {}, job_id=1, access_token="prefetched-token")
    worker.run()

    assert received["access_token"] == "prefetched-token"
