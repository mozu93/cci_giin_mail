from app.ui.send_tab import _SendWorker, _CONSECUTIVE_ERROR_LIMIT


class _FakeSession:
    def close(self):
        pass


def test_aborts_after_consecutive_error_limit(monkeypatch):
    def fake_send_mail(graph_config, to_addr, subject, body, attachments,
                       access_token=None):
        raise RuntimeError("接続エラー")

    logged = []

    def fake_add_log(session, job_id, member_id, to_addr, subject, status, error=None):
        logged.append((to_addr, status))

    monkeypatch.setattr("app.ui.send_tab.send_mail", fake_send_mail)
    monkeypatch.setattr("app.ui.send_tab.add_log", fake_add_log)
    monkeypatch.setattr("app.ui.send_tab.get_session", lambda: _FakeSession())
    monkeypatch.setattr("app.ui.send_tab.time.sleep", lambda s: None)

    targets = [
        {"to_address": f"a{i}@example.com", "subject": "s", "body": "b",
         "org_name": f"org{i}", "member_id": i, "attachments": []}
        for i in range(_CONSECUTIVE_ERROR_LIMIT + 3)
    ]
    worker = _SendWorker(targets, {}, job_id=1, access_token="token")

    results = {}
    worker.finished.connect(lambda s, e, sk: results.update(success=s, error=e, skip=sk))
    worker.run()

    assert results["error"] == _CONSECUTIVE_ERROR_LIMIT
    assert results["skip"] == 3
    error_logs = [s for _, s in logged if s == "error"]
    skip_logs = [s for _, s in logged if s == "skip"]
    assert len(error_logs) == _CONSECUTIVE_ERROR_LIMIT
    assert len(skip_logs) == 3


def test_does_not_abort_when_errors_are_not_consecutive(monkeypatch):
    call_count = {"n": 0}

    def fake_send_mail(graph_config, to_addr, subject, body, attachments,
                       access_token=None):
        call_count["n"] += 1
        if call_count["n"] % 2 == 0:
            raise RuntimeError("時々失敗")

    monkeypatch.setattr("app.ui.send_tab.send_mail", fake_send_mail)
    monkeypatch.setattr("app.ui.send_tab.add_log", lambda *a, **k: None)
    monkeypatch.setattr("app.ui.send_tab.get_session", lambda: _FakeSession())
    monkeypatch.setattr("app.ui.send_tab.time.sleep", lambda s: None)

    n = _CONSECUTIVE_ERROR_LIMIT * 2 + 1
    targets = [
        {"to_address": f"a{i}@example.com", "subject": "s", "body": "b",
         "org_name": f"org{i}", "member_id": i, "attachments": []}
        for i in range(n)
    ]
    worker = _SendWorker(targets, {}, job_id=1, access_token="token")
    results = {}
    worker.finished.connect(lambda s, e, sk: results.update(success=s, error=e, skip=sk))
    worker.run()

    assert results["skip"] == 0
    assert results["success"] + results["error"] == n
