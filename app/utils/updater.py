# -*- coding: utf-8 -*-
import os
import sys
import json
import hashlib
import tempfile
import subprocess
import urllib.request
import urllib.error
from urllib.parse import urlparse
from typing import Optional

from packaging.version import Version

GITHUB_API_URL = "https://api.github.com/repos/mozu93/cci_giin_mail/releases/latest"
_TIMEOUT = 8
_ALLOWED_DOWNLOAD_HOSTS = {"github.com", "objects.githubusercontent.com"}


def _is_allowed_download_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme == "https" and parsed.hostname in _ALLOWED_DOWNLOAD_HOSTS


def _parse_sha256(value: str) -> str:
    digest = value.strip().split()[0].lower() if value.strip() else ""
    if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
        raise ValueError("SHA-256チェックサムの形式が不正です。")
    return digest


def is_newer_version(current: str, latest: str) -> bool:
    """latest が current より新しければ True。v プレフィックスは除去する。"""
    current = current.lstrip("v")
    latest  = latest.lstrip("v")
    return Version(latest) > Version(current)


def check_latest_version_detailed() -> tuple[Optional[dict], str]:
    """
    GitHub API で最新リリースを取得する。
    戻り値: (リリース情報, エラーメッセージ)。
    成功時はエラーメッセージが空文字、失敗時はリリース情報が None。
    """
    try:
        req = urllib.request.Request(
            GITHUB_API_URL,
            headers={"Accept": "application/vnd.github+json",
                     "User-Agent": "cci-mail-updater"},
        )
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        tag = data.get("tag_name", "")
        assets = data.get("assets", [])
        if not tag or not assets:
            return None, "公開済みのリリース情報を取得できませんでした。"
        installer = next(
            (asset for asset in assets
             if asset.get("name", "").lower().startswith("ccimail_setup_")
             and asset.get("name", "").lower().endswith(".exe")),
            None,
        )
        checksum = next(
            (asset for asset in assets
             if installer and asset.get("name", "").lower()
             == (installer.get("name", "") + ".sha256").lower()),
            None,
        )
        download_url = installer.get("browser_download_url", "") if installer else ""
        checksum_url = checksum.get("browser_download_url", "") if checksum else ""
        if (not download_url or not checksum_url
                or not _is_allowed_download_url(download_url)
                or not _is_allowed_download_url(checksum_url)):
            return None, (
                "更新ファイルまたは安全確認用ファイルが見つかりませんでした。")
        checksum_req = urllib.request.Request(
            checksum_url, headers={"User-Agent": "cci-mail-updater"})
        with urllib.request.urlopen(checksum_req, timeout=_TIMEOUT) as response:
            if not _is_allowed_download_url(response.geturl()):
                return None, "更新ファイルの配布先を安全に確認できませんでした。"
            expected_sha256 = _parse_sha256(
                response.read(512).decode("ascii", errors="strict"))
        return {
            "tag_name": tag,
            "download_url": download_url,
            "expected_sha256": expected_sha256,
        }, ""
    except urllib.error.HTTPError as exc:
        return None, f"更新サーバーから応答エラーが返されました（HTTP {exc.code}）。"
    except urllib.error.URLError:
        return None, (
            "更新サーバーへ接続できませんでした。"
            "インターネット接続または社内ネットワークの制限を確認してください。")
    except TimeoutError:
        return None, "更新サーバーへの接続がタイムアウトしました。"
    except Exception:
        return None, "更新情報の確認中にエラーが発生しました。"


def check_latest_version() -> Optional[dict]:
    """従来互換の更新確認。失敗時は None を返す。"""
    result, _error = check_latest_version_detailed()
    return result


def download_new_exe(url: str, expected_sha256: str,
                     progress_callback=None) -> Optional[str]:
    """
    新しいインストーラー exe を %TEMP% にダウンロードする。
    progress_callback(received_bytes, total_bytes) を呼び出す（total が不明な場合は -1）。
    成功時はダウンロード先パスを返す。失敗時は None。
    """
    if not _is_allowed_download_url(url):
        return None
    try:
        expected_sha256 = _parse_sha256(expected_sha256)
    except ValueError:
        return None
    tmp_path = None
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "cci-mail-updater"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            if not _is_allowed_download_url(resp.geturl()):
                return None
            total = int(resp.headers.get("Content-Length", -1))
            fd, tmp_path = tempfile.mkstemp(suffix=".exe", prefix="cci_mail_new_")
            received = 0
            digest = hashlib.sha256()
            with os.fdopen(fd, "wb") as f:
                while True:
                    chunk = resp.read(65536)
                    if not chunk:
                        break
                    f.write(chunk)
                    digest.update(chunk)
                    received += len(chunk)
                    if progress_callback:
                        progress_callback(received, total)
        if digest.hexdigest() != expected_sha256:
            os.unlink(tmp_path)
            return None
        return tmp_path
    except Exception:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
        return None


def launch_updater(new_exe_path: str, current_exe_path: str):
    """
    updater.bat を %TEMP% に生成して起動し、アプリを終了する。
    bat は: 3秒待機（アプリ終了を待つ）→ インストーラーを起動 → 自己削除
    """
    bat_fd, bat_path = tempfile.mkstemp(suffix=".bat", prefix="cci_mail_updater_")
    with os.fdopen(bat_fd, "w", encoding="cp932") as f:
        f.write("@echo off\r\n")
        f.write("timeout /t 3 /nobreak > nul\r\n")
        f.write(f'start "" "{new_exe_path}"\r\n')
        f.write('del "%~f0"\r\n')
    subprocess.Popen(["cmd", "/c", bat_path], creationflags=subprocess.CREATE_NO_WINDOW)
    sys.exit(0)
