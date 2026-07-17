from unittest.mock import MagicMock
from pathlib import Path
from app.services import email_service


def _patch_msal(monkeypatch, cache_file):
    """既存テストと共通のmsal/persistenceモックをセットアップするヘルパー。"""
    fake_persistence = object()
    build_calls = []

    def fake_build_encrypted_persistence(location):
        build_calls.append(location)
        return fake_persistence

    fake_cache = object()
    cache_calls = []

    def fake_persisted_cache(persistence):
        cache_calls.append(persistence)
        return fake_cache

    monkeypatch.setattr(email_service, "build_encrypted_persistence",
                        fake_build_encrypted_persistence)
    monkeypatch.setattr(email_service, "PersistedTokenCache", fake_persisted_cache)

    fake_app = MagicMock()
    fake_app.get_accounts.return_value = []
    fake_app.acquire_token_interactive.return_value = {"access_token": "abc123"}
    captured_kwargs = {}

    def fake_pca(**kwargs):
        captured_kwargs.update(kwargs)
        return fake_app

    monkeypatch.setattr(email_service.msal, "PublicClientApplication", fake_pca)

    return build_calls, cache_calls, captured_kwargs, fake_persistence, fake_cache


def test_get_access_token_uses_encrypted_persistence(monkeypatch, tmp_path):
    cache_file = tmp_path / "cache.bin"
    legacy_file = tmp_path / "legacy.bin"
    monkeypatch.setattr(email_service, "_CACHE_FILE", cache_file)
    monkeypatch.setattr(email_service, "_LEGACY_CACHE_FILE", legacy_file)

    build_calls, cache_calls, captured_kwargs, fake_persistence, fake_cache = _patch_msal(monkeypatch, cache_file)

    token = email_service.get_access_token({"client_id": "cid", "tenant_id": "tid"})

    assert token == "abc123"
    assert build_calls == [str(cache_file)]
    assert cache_calls == [fake_persistence]
    assert captured_kwargs["token_cache"] is fake_cache


def test_get_access_token_removes_legacy_plaintext_cache(monkeypatch, tmp_path):
    """旧・平文キャッシュファイルが存在する場合、新キャッシュ生成時に削除されること。"""
    cache_file = tmp_path / "cache.bin"
    legacy_file = tmp_path / "legacy.bin"
    legacy_file.parent.mkdir(parents=True, exist_ok=True)
    legacy_file.write_text("plaintext-token-cache-content")
    monkeypatch.setattr(email_service, "_CACHE_FILE", cache_file)
    monkeypatch.setattr(email_service, "_LEGACY_CACHE_FILE", legacy_file)

    _patch_msal(monkeypatch, cache_file)

    assert legacy_file.exists()

    token = email_service.get_access_token({"client_id": "cid", "tenant_id": "tid"})

    assert token == "abc123"
    assert not legacy_file.exists()


def test_get_access_token_survives_legacy_cleanup_failure(monkeypatch, tmp_path):
    """旧キャッシュ削除が失敗しても、認証処理自体は成功すること。"""
    cache_file = tmp_path / "cache.bin"
    legacy_file = tmp_path / "legacy.bin"
    monkeypatch.setattr(email_service, "_CACHE_FILE", cache_file)
    monkeypatch.setattr(email_service, "_LEGACY_CACHE_FILE", legacy_file)

    def fake_unlink(self, missing_ok=False):
        raise OSError("permission denied")

    monkeypatch.setattr(Path, "unlink", fake_unlink)

    _patch_msal(monkeypatch, cache_file)

    token = email_service.get_access_token({"client_id": "cid", "tenant_id": "tid"})

    assert token == "abc123"
