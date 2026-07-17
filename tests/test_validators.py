import pytest
from app.utils.validators import is_valid_email


@pytest.mark.parametrize("address", [
    "yamada@example.com",
    "somu.tantou@example.co.jp",
    "a+tag@example.com",
])
def test_is_valid_email_accepts_valid_addresses(address):
    assert is_valid_email(address) is True


@pytest.mark.parametrize("address", [
    "",
    "yamada",
    "yamada@",
    "@example.com",
    "yamada@example",
    "yamada @example.com",
    "yamada@ example.com",
])
def test_is_valid_email_rejects_invalid_addresses(address):
    assert is_valid_email(address) is False
