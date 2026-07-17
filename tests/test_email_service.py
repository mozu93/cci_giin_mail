import pytest
from app.services.email_service import render_body, build_message


class _FakeResponse:
    def __init__(self, status_code, text="", headers=None):
        self.status_code = status_code
        self.text = text
        self.headers = headers or {}


def test_render_body_basic():
    template = "こんにちは、{事業所名}の{氏名}様。"
    context = {"事業所名": "○○商事", "氏名": "山田 太郎"}
    result = render_body(template, context)
    assert result == "こんにちは、○○商事の山田 太郎様。"


def test_render_body_col_placeholders():
    template = "案件: {col1}、金額: {col2}"
    context = {"col1": "総会", "col2": "5,000円", "col3": "", "col4": "", "col5": ""}
    result = render_body(template, context)
    assert result == "案件: 総会、金額: 5,000円"


def test_render_body_missing_key_becomes_empty():
    template = "こんにちは {氏名}様。{col1}"
    context = {"氏名": "山田 太郎"}
    result = render_body(template, context)
    assert "{col1}" not in result
    assert "山田 太郎" in result


def test_render_body_all_placeholders():
    template = "{事業所名} {役職名} {氏名} {会議所役職名} {col1} {col2} {col3} {col4} {col5}"
    context = {
        "事業所名": "A社", "役職名": "社長", "氏名": "田中",
        "会議所役職名": "議員", "col1": "1", "col2": "2",
        "col3": "3", "col4": "4", "col5": "5",
    }
    result = render_body(template, context)
    assert result == "A社 社長 田中 議員 1 2 3 4 5"


def test_build_message_structure():
    msg = build_message(
        to_address="test@example.com",
        subject="テスト",
        body="本文テスト",
        attachments=[],
    )
    assert msg["message"]["toRecipients"][0]["emailAddress"]["address"] == "test@example.com"
    assert msg["message"]["subject"] == "テスト"
    assert msg["message"]["body"]["content"] == "本文テスト"
    assert msg["message"]["attachments"] == []


def test_build_message_with_attachment(tmp_path):
    f = tmp_path / "test.txt"
    f.write_text("hello", encoding="utf-8")
    msg = build_message("to@example.com", "件名", "本文", [str(f)])
    attachments = msg["message"]["attachments"]
    assert len(attachments) == 1
    assert attachments[0]["name"] == "test.txt"
    assert attachments[0]["@odata.type"] == "#microsoft.graph.fileAttachment"


def test_send_mail_uses_provided_access_token_without_fetching(monkeypatch):
    from app.services import email_service

    def fail_get_token(graph_config):
        raise AssertionError("access_token指定時はget_access_tokenを呼んではいけない")

    monkeypatch.setattr(email_service, "get_access_token", fail_get_token)
    monkeypatch.setattr(email_service.requests, "post",
                         lambda *a, **k: _FakeResponse(202))

    email_service.send_mail({}, "to@example.com", "件名", "本文",
                            access_token="provided-token")


def test_send_mail_retries_on_429_then_succeeds(monkeypatch):
    from app.services import email_service

    responses = [_FakeResponse(429, headers={"Retry-After": "1"}), _FakeResponse(202)]
    sleep_calls = []

    monkeypatch.setattr(email_service.requests, "post",
                         lambda *a, **k: responses.pop(0))
    monkeypatch.setattr(email_service.time, "sleep",
                         lambda s: sleep_calls.append(s))

    email_service.send_mail({}, "to@example.com", "件名", "本文",
                            access_token="token")

    assert sleep_calls == [1]


def test_send_mail_raises_after_max_429_retries(monkeypatch):
    from app.services import email_service

    monkeypatch.setattr(email_service.requests, "post",
                         lambda *a, **k: _FakeResponse(
                             429, text="rate limited", headers={"Retry-After": "1"}))
    monkeypatch.setattr(email_service.time, "sleep", lambda s: None)

    with pytest.raises(RuntimeError):
        email_service.send_mail({}, "to@example.com", "件名", "本文",
                                access_token="token")


def test_build_message_missing_attachment_raises(tmp_path):
    missing = str(tmp_path / "missing.pdf")
    with pytest.raises(FileNotFoundError):
        build_message("to@example.com", "件名", "本文", [missing])


def test_send_mail_raises_for_missing_attachment_without_http_call(tmp_path, monkeypatch):
    from app.services import email_service

    def fail_post(*args, **kwargs):
        raise AssertionError("添付ファイルが無い場合はHTTPリクエストを送ってはいけない")

    monkeypatch.setattr(email_service.requests, "post", fail_post)
    missing = str(tmp_path / "missing.pdf")

    with pytest.raises(FileNotFoundError):
        email_service.send_mail({}, "to@example.com", "件名", "本文",
                                attachments=[missing], access_token="token")
