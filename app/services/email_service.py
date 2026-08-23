import base64
import os
import re
import time
import requests
import msal
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from urllib.parse import quote
from pathlib import Path
from msal_extensions import build_encrypted_persistence, PersistedTokenCache

_ALL_KEYS = ["事業所名", "役職名", "氏名", "会議所役職名",
             "col1", "col2", "col3", "col4", "col5"]

_SEND_SCOPES = ["https://graph.microsoft.com/Mail.Send"]
_READ_SCOPES = ["https://graph.microsoft.com/Mail.Read"]
_SEND_SHARED_SCOPE = "https://graph.microsoft.com/Mail.Send.Shared"
_TRACE_SCOPE = ["https://graph.microsoft.com/.default"]
_CACHE_FILE = Path.home() / ".cci-mail" / "m365_token_cache_v2.bin"
_LEGACY_CACHE_FILE = Path.home() / ".cci-mail" / "m365_token_cache.bin"


def _public_client(graph_config: dict):
    if not graph_config.get("client_id") or not graph_config.get("tenant_id"):
        raise ValueError("テナントIDとクライアントIDを設定してください。")
    _CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    persistence = build_encrypted_persistence(str(_CACHE_FILE))
    cache = PersistedTokenCache(persistence)
    return msal.PublicClientApplication(
        client_id=graph_config["client_id"],
        authority=f"https://login.microsoftonline.com/{graph_config['tenant_id']}",
        token_cache=cache,
    )


def get_cached_account_usernames(graph_config: dict) -> list[str]:
    app = _public_client(graph_config)
    return sorted({
        account.get("username", "")
        for account in app.get_accounts()
        if account.get("username")
    })


def render_body(template: str, context: dict) -> str:
    for key in _ALL_KEYS:
        placeholder = f"{{{key}}}"
        value = str(context.get(key, ""))
        template = template.replace(placeholder, value)
    return template


def parse_recipient_addresses(value: str) -> list[str]:
    return [
        address.strip() for address in re.split(r"[,;\n]", value or "")
        if address.strip()
    ]


def build_message(to_address: str, subject: str, body: str,
                  attachments: list[str], from_address: str = "",
                  cc_addresses: list[str] | None = None,
                  bcc_addresses: list[str] | None = None) -> dict:
    attachment_list = []
    for path in attachments:
        if not os.path.exists(path):
            raise FileNotFoundError(f"添付ファイルが見つかりません: {path}")
        with open(path, "rb") as f:
            content = base64.b64encode(f.read()).decode("utf-8")
        attachment_list.append({
            "@odata.type":  "#microsoft.graph.fileAttachment",
            "name":         os.path.basename(path),
            "contentBytes": content,
        })
    message = {
        "subject": subject,
        "body": {
            "contentType": "Text",
            "content":     body,
        },
        "toRecipients": [
            {"emailAddress": {"address": to_address}}
        ],
        "ccRecipients": [
            {"emailAddress": {"address": address}}
            for address in (cc_addresses or [])
        ],
        "bccRecipients": [
            {"emailAddress": {"address": address}}
            for address in (bcc_addresses or [])
        ],
        "attachments": attachment_list,
    }
    if from_address:
        message["from"] = {"emailAddress": {"address": from_address}}

    return {
        "message": message,
        "saveToSentItems": "true",
    }


ATTACHMENT_SIZE_LIMIT_BYTES = 3 * 1024 * 1024  # Graph sendMail直添付の実用上限（約3MB）


def total_attachment_size(paths: list[str]) -> int:
    return sum(os.path.getsize(p) for p in paths if os.path.exists(p))


def compile_send_targets(
    checked_rows: list[dict],
    subject_tpl: str,
    body_tpl: str,
    sig_body: str,
    merge_data: dict,
    col_labels: dict,
    common_attachments: list,
    attach_map: dict,
) -> list[dict]:
    """チェック済み行リスト → 送信ターゲット dict リスト（純変換）。

    checked_rows の各要素: {"member": Member, "to_address": str}
    to_address が空文字の場合はメール無しとして扱う（送信時スキップ対象）。
    """
    targets = []
    for row in checked_rows:
        m = row["member"]
        to_addr = row["to_address"]
        merge = merge_data.get(m.member_number, {})
        context = {
            "事業所名":     m.organization_name,
            "役職名":       m.title or "",
            "氏名":         m.name,
            "会議所役職名": m.position.name if m.position else "",
            **{k: merge.get(k, "") for k in ["col1", "col2", "col3", "col4", "col5"]},
        }
        for col_key, label in col_labels.items():
            context[label] = context.get(col_key, "")
        targets.append({
            "member_id":   m.id,
            "org_name":    m.organization_name,
            "name":        m.name,
            "to_address":  to_addr,
            "subject":     render_body(subject_tpl, context),
            "body":        render_body(body_tpl + sig_body, context),
            "attachments": list(common_attachments) + attach_map.get(m.member_number, []),
        })
    return targets


def apply_test_mode(targets: list[dict], test_address: str) -> list[dict]:
    """本来の宛先を明記しつつ、全メールを安全なテスト送信先へ振り替える。"""
    if not test_address.strip():
        raise ValueError("テストモードにはテスト送信先の設定が必要です。")
    converted = []
    for target in targets:
        original_to = target.get("to_address", "")
        original_cc = list(target.get("cc_addresses", []))
        original_bcc = list(target.get("bcc_addresses", []))
        notice = (
            "【テストモードで送信しています】\n"
            f"本来のTo: {original_to or 'なし'}\n"
            f"本来のCC: {', '.join(original_cc) or 'なし'}\n"
            f"本来のBCC: {', '.join(original_bcc) or 'なし'}\n"
            "────────────────────\n\n"
        )
        converted.append({
            **target,
            "original_to_address": original_to,
            "original_cc_addresses": original_cc,
            "original_bcc_addresses": original_bcc,
            "to_address": test_address.strip(),
            "cc_addresses": [],
            "bcc_addresses": [],
            "subject": f"【テストモード】{target.get('subject', '')}",
            "body": notice + target.get("body", ""),
        })
    return converted


def get_access_token(graph_config: dict, purpose: str = "send",
                     return_account: bool = False) -> str | tuple[str, str]:
    try:
        _LEGACY_CACHE_FILE.unlink(missing_ok=True)
    except OSError:
        pass
    app = _public_client(graph_config)

    if purpose == "send":
        scopes = list(_SEND_SCOPES)
    elif purpose == "attendance_read":
        scopes = list(_READ_SCOPES)
    else:
        raise ValueError(f"不明な認証用途です: {purpose}")
    if purpose == "send" and graph_config.get("from_address", "").strip():
        scopes.append(_SEND_SHARED_SCOPE)

    result = None
    accounts = app.get_accounts()
    selected_username = graph_config.get("account_username", "").strip().casefold()
    selected = next(
        (account for account in accounts
         if account.get("username", "").casefold() == selected_username),
        None,
    )
    if not selected and len(accounts) == 1:
        selected = accounts[0]
    if not selected and len(accounts) > 1:
        raise RuntimeError(
            "複数のMicrosoft 365アカウントが保存されています。"
            "設定画面で送信に使用するアカウントを確認してください。")
    if selected:
        result = app.acquire_token_silent(scopes, account=selected)

    if not result:
        result = app.acquire_token_interactive(scopes=scopes)

    if not result or "access_token" not in result:
        desc = result.get("error_description", str(result)) if result else "不明なエラー"
        raise RuntimeError(f"Microsoft 365 認証に失敗しました: {desc}")

    username = (
        result.get("id_token_claims", {}).get("preferred_username")
        or (selected or {}).get("username")
        or ""
    )
    if return_account:
        return result["access_token"], username
    return result["access_token"]


def sanitize_graph_error(status_code: int, response_text: str = "") -> str:
    """履歴に個人情報を含むGraphレスポンス本文を保存しない。"""
    messages = {
        400: "送信内容をMicrosoft Graphが受け付けませんでした",
        401: "Microsoft 365の認証が無効です",
        403: "メール送信権限がありません",
        404: "送信先リソースが見つかりません",
        429: "Microsoft 365の送信制限に達しました",
    }
    return f"送信失敗 ({status_code}): {messages.get(status_code, 'Microsoft Graphでエラーが発生しました')}"


_MAX_RATE_LIMIT_RETRIES = 3
_DEFAULT_RETRY_AFTER_SECONDS = 5


def send_mail(graph_config: dict, to_address: str, subject: str,
              body: str, attachments: list[str] | None = None,
              cc_addresses: list[str] | None = None,
              bcc_addresses: list[str] | None = None,
              access_token: str | None = None) -> None:
    token = access_token or get_access_token(graph_config)
    payload = build_message(
        to_address, subject, body, attachments or [],
        graph_config.get("from_address", "").strip(),
        cc_addresses=cc_addresses, bcc_addresses=bcc_addresses)
    headers = {"Authorization": f"Bearer {token}",
               "Content-Type": "application/json"}
    attempt = 0
    while True:
        resp = requests.post(
            "https://graph.microsoft.com/v1.0/me/sendMail",
            headers=headers,
            json=payload,
            timeout=30,
        )
        if resp.status_code in (200, 202):
            return
        if resp.status_code == 429 and attempt < _MAX_RATE_LIMIT_RETRIES:
            try:
                wait_seconds = int(resp.headers.get(
                    "Retry-After", _DEFAULT_RETRY_AFTER_SECONDS))
            except ValueError:
                wait_seconds = _DEFAULT_RETRY_AFTER_SECONDS
            time.sleep(wait_seconds)
            attempt += 1
            continue
        raise RuntimeError(sanitize_graph_error(resp.status_code, resp.text))


def send_test_mail(graph_config: dict, subject: str, body: str,
                   attachments: list[str] | None = None) -> None:
    test_address = graph_config.get("test_address", "")
    if not test_address:
        raise ValueError("テスト送信先アドレスが設定されていません。")
    send_mail(graph_config, test_address, f"【テスト】{subject}", body,
              attachments or [])


def get_trace_access_token(graph_config: dict) -> str:
    """メッセージ追跡API用のアプリケーション権限トークンを取得する。"""
    client_secret = graph_config.get("trace_client_secret", "").strip()
    if not client_secret:
        raise ValueError(
            "配信状況の確認には、設定画面でメッセージ追跡用の"
            "クライアントシークレットを設定してください。")
    tenant_id = graph_config.get("tenant_id", "").strip()
    client_id = graph_config.get("client_id", "").strip()
    if not tenant_id or not client_id:
        raise ValueError("テナントIDとクライアントIDを設定してください。")
    app = msal.ConfidentialClientApplication(
        client_id=client_id,
        client_credential=client_secret,
        authority=f"https://login.microsoftonline.com/{tenant_id}",
    )
    result = app.acquire_token_for_client(scopes=_TRACE_SCOPE)
    if not result or "access_token" not in result:
        desc = result.get("error_description", str(result)) if result else "不明なエラー"
        raise RuntimeError(f"配信状況確認の認証に失敗しました: {desc}")
    return result["access_token"]


def get_delivery_trace(graph_config: dict, to_address: str,
                       subject: str, sent_at: datetime | None) -> dict:
    """Exchange Onlineのメッセージ追跡結果を1宛先分取得する。

    sendMailの受付結果とは別に、Exchange Online内部での配信状態を返す。
    状態がまだ生成されていない場合は ``pending`` とする。
    """
    if not sent_at:
        return {"status": "unknown", "message": "送信日時がありません。"}
    sender = (graph_config.get("trace_sender_address", "") or
              graph_config.get("from_address", "") or
              graph_config.get("account_username", "")).strip()
    if not sender:
        return {"status": "unknown", "message": "送信元アドレスを特定できません。"}

    token = get_trace_access_token(graph_config)
    # sent_atは既存DBでは日本時間のローカル時刻（タイムゾーンなし）で保存されている。
    # Message Trace APIはUTCを返すため、日本時間として解釈してからUTCへ変換する。
    local_zone = ZoneInfo("Asia/Tokyo")
    sent_at_utc = sent_at.replace(tzinfo=local_zone).astimezone(timezone.utc)
    start = sent_at_utc - timedelta(hours=2)
    end = sent_at_utc + timedelta(days=3)
    odata_filter = (
        f"recipientAddress eq '{to_address.replace(chr(39), chr(39) * 2)}' "
        f"and senderAddress eq '{sender.replace(chr(39), chr(39) * 2)}' "
        f"and receivedDateTime ge {start.isoformat().replace('+00:00', 'Z')} "
        f"and receivedDateTime le {end.isoformat().replace('+00:00', 'Z')}"
    )
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.get(
        "https://graph.microsoft.com/v1.0/admin/exchange/tracing/messageTraces",
        headers=headers,
        params={"$filter": odata_filter, "$top": "50"},
        timeout=30,
    )
    if resp.status_code != 200:
        raise RuntimeError(sanitize_graph_error(resp.status_code, resp.text))
    values = resp.json().get("value", [])
    # 同じ宛先・時刻に複数候補がある場合は件名一致を優先する。
    subject_matches = [item for item in values if item.get("subject") == subject]
    item = (subject_matches or values)
    if not item:
        return {"status": "pending", "message": "追跡情報がまだ反映されていません。"}
    trace = sorted(item, key=lambda value: value.get("receivedDateTime", ""), reverse=True)[0]
    status = str(trace.get("status", "unknown")).lower()
    message = {
        "delivered": "Microsoft 365で配信済みです。",
        "failed": "Microsoft 365で配信に失敗しました。",
        "pending": "Microsoft 365で処理中です。",
        "quarantined": "隔離されています。",
        "filteredasspam": "スパムとして処理されました。",
    }.get(status, f"Microsoft 365の状態: {status}")
    if status == "failed":
        trace_id = trace.get("id")
        if trace_id:
            detail_url = (
                "https://graph.microsoft.com/v1.0/admin/exchange/tracing/"
                f"messageTraces/{quote(str(trace_id), safe='')}"
                f"/getDetailsByRecipient(recipientAddress='{quote(to_address, safe='@._-')}')"
            )
            detail_resp = requests.get(detail_url, headers=headers, timeout=30)
            if detail_resp.status_code == 200:
                details = detail_resp.json().get("value", [])
                descriptions = [d.get("description", "") for d in details
                                if d.get("description")]
                if descriptions:
                    message += "\n" + descriptions[-1]
    return {"status": status, "message": message}
