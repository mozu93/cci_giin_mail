from unittest.mock import MagicMock
from app.services import email_service


def test_get_access_token_uses_encrypted_persistence(monkeypatch, tmp_path):
    cache_file = tmp_path / "cache.bin"
    monkeypatch.setattr(email_service, "_CACHE_FILE", cache_file)

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

    token = email_service.get_access_token({"client_id": "cid", "tenant_id": "tid"})

    assert token == "abc123"
    assert build_calls == [str(cache_file)]
    assert cache_calls == [fake_persistence]
    assert captured_kwargs["token_cache"] is fake_cache
