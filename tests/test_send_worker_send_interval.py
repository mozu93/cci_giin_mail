from app.ui.send_tab import _SendWorker, _SEND_INTERVAL_SECONDS


class _FakeSession:
    def close(self):
        pass


def test_sleeps_between_sends_but_not_after_last(monkeypatch):
    sleep_calls = []

    monkeypatch.setattr("app.ui.send_tab.send_mail", lambda *a, **k: None)
    monkeypatch.setattr("app.ui.send_tab.add_log", lambda *a, **k: None)
    monkeypatch.setattr("app.ui.send_tab.get_session", lambda: _FakeSession())
    monkeypatch.setattr("app.ui.send_tab.time.sleep",
                         lambda s: sleep_calls.append(s))

    targets = [
        {"to_address": f"a{i}@example.com", "subject": "s", "body": "b",
         "org_name": f"org{i}", "member_id": i, "attachments": []}
        for i in range(3)
    ]
    worker = _SendWorker(targets, {}, job_id=1, access_token="token")
    worker.run()

    assert sleep_calls == [_SEND_INTERVAL_SECONDS, _SEND_INTERVAL_SECONDS]
