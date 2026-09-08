import pytest
from app.ui.send_tab import _SendWorker


def test_cancel_stops_before_remaining_targets(monkeypatch):
    sent = []

    def fake_send_mail(graph_config, to_addr, subject, body, attachments,
                       access_token=None):
        sent.append(to_addr)
        if len(sent) == 1:
            worker.request_cancel()

    def fake_add_log(session, job_id, member_id, to_addr, subject, status,
                     error=None, **kwargs):
        pass

    monkeypatch.setattr("app.ui.send_tab.send_mail", fake_send_mail)
    monkeypatch.setattr("app.ui.send_tab.add_log", fake_add_log)
    monkeypatch.setattr("app.ui.send_tab.get_session", lambda: _FakeSession())
    monkeypatch.setattr("app.ui.send_tab.time.sleep", lambda s: None)

    targets = [
        {"to_address": f"a{i}@example.com", "subject": "s", "body": "b",
         "org_name": f"org{i}", "member_id": i, "attachments": []}
        for i in range(5)
    ]
    worker = _SendWorker(targets, {}, job_id=1, access_token="token")
    worker.run()

    assert sent == ["a0@example.com"]


def test_cancel_logs_remaining_targets_as_skip(monkeypatch):
    logged = []

    def fake_send_mail(graph_config, to_addr, subject, body, attachments,
                       access_token=None):
        logged.append((to_addr, "sent"))
        if len(logged) == 1:
            worker.request_cancel()

    def fake_add_log(session, job_id, member_id, to_addr, subject, status,
                     error=None, **kwargs):
        logged.append((to_addr, status))

    monkeypatch.setattr("app.ui.send_tab.send_mail", fake_send_mail)
    monkeypatch.setattr("app.ui.send_tab.add_log", fake_add_log)
    monkeypatch.setattr("app.ui.send_tab.get_session", lambda: _FakeSession())
    monkeypatch.setattr("app.ui.send_tab.time.sleep", lambda s: None)

    targets = [
        {"to_address": f"a{i}@example.com", "subject": "s", "body": "b",
         "org_name": f"org{i}", "member_id": i, "attachments": []}
        for i in range(5)
    ]
    worker = _SendWorker(targets, {}, job_id=1, access_token="token")
    worker.run()

    skip_logs = [addr for addr, status in logged if status == "skip"]
    assert skip_logs == ["a1@example.com", "a2@example.com",
                         "a3@example.com", "a4@example.com"]


class _FakeSession:
    def close(self):
        pass
