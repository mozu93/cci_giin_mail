import base64
import os
import re
import requests
import msal

_ALL_KEYS = ["事業所名", "役職名", "氏名", "会議所役職名",
             "col1", "col2", "col3", "col4", "col5"]


def render_body(template: str, context: dict) -> str:
    for key in _ALL_KEYS:
        placeholder = f"{{{key}}}"
        value = str(context.get(key, ""))
        template = template.replace(placeholder, value)
    return template


def build_message(to_address: str, subject: str, body: str,
                  attachments: list[str]) -> dict:
    attachment_list = []
    for path in attachments:
        if not os.path.exists(path):
            continue
        with open(path, "rb") as f:
            content = base64.b64encode(f.read()).decode("utf-8")
        attachment_list.append({
            "@odata.type":  "#microsoft.graph.fileAttachment",
            "name":         os.path.basename(path),
            "contentBytes": content,
        })
    return {
        "message": {
            "subject": subject,
            "body": {
                "contentType": "Text",
                "content":     body,
            },
            "toRecipients": [
                {"emailAddress": {"address": to_address}}
            ],
            "attachments": attachment_list,
        },
        "saveToSentItems": "true",
    }


def get_access_token(graph_config: dict) -> str:
    app = msal.ConfidentialClientApplication(
        graph_config["client_id"],
        authority=f"https://login.microsoftonline.com/{graph_config['tenant_id']}",
        client_credential=graph_config["client_secret"],
    )
    result = app.acquire_token_for_client(
        scopes=["https://graph.microsoft.com/.default"]
    )
    if "access_token" not in result:
        raise RuntimeError(
            f"トークン取得失敗: {result.get('error_description', str(result))}"
        )
    return result["access_token"]


def send_mail(graph_config: dict, to_address: str, subject: str,
              body: str, attachments: list[str] | None = None) -> None:
    token = get_access_token(graph_config)
    from_address = graph_config["from_address"]
    payload = build_message(to_address, subject, body, attachments or [])
    url = f"https://graph.microsoft.com/v1.0/users/{from_address}/sendMail"
    resp = requests.post(
        url,
        headers={"Authorization": f"Bearer {token}",
                 "Content-Type": "application/json"},
        json=payload,
        timeout=30,
    )
    if resp.status_code not in (200, 202):
        raise RuntimeError(
            f"送信失敗 ({resp.status_code}): {resp.text[:200]}"
        )


def send_test_mail(graph_config: dict, subject: str, body: str) -> None:
    test_address = graph_config.get("test_address", "")
    if not test_address:
        raise ValueError("テスト送信先アドレスが設定されていません。")
    send_mail(graph_config, test_address, f"【テスト】{subject}", body)
