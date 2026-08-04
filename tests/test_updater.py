import pytest

from app.utils.updater import (
    _is_allowed_download_url, _parse_sha256, check_latest_version_detailed,
)


def test_update_download_only_allows_expected_github_hosts():
    assert _is_allowed_download_url(
        "https://github.com/mozu93/cci_giin_mail/releases/download/v1/setup.exe")
    assert _is_allowed_download_url(
        "https://objects.githubusercontent.com/release/setup.exe")
    assert _is_allowed_download_url(
        "https://release-assets.githubusercontent.com/release/setup.exe")
    assert not _is_allowed_download_url("http://github.com/setup.exe")
    assert not _is_allowed_download_url("https://github.com.example.test/setup.exe")


def test_parse_sha256_accepts_standard_checksum_line():
    digest = "a" * 64
    assert _parse_sha256(f"{digest}  setup.exe\n") == digest


def test_parse_sha256_rejects_invalid_value():
    with pytest.raises(ValueError):
        _parse_sha256("not-a-checksum")


def test_detailed_update_check_reports_network_error(monkeypatch):
    from app.utils import updater

    def fail_open(*args, **kwargs):
        raise updater.urllib.error.URLError("blocked")

    monkeypatch.setattr(updater.urllib.request, "urlopen", fail_open)

    result, error = check_latest_version_detailed()

    assert result is None
    assert "接続できません" in error
