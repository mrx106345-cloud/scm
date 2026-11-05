"""Credential encryption + masking tests (P4-04, acceptance D3)."""

from __future__ import annotations

import base64

import pytest

from app.core.crypto import (
    CryptoError,
    decrypt_config,
    encrypt_config,
    is_secret_key,
    mask_config,
)

_KEY = base64.b64encode(b"0123456789abcdef0123456789abcdef").decode()


@pytest.fixture(autouse=True)
def _env_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SCM_CREDENTIAL_KEY", _KEY)


def test_encrypt_decrypt_roundtrip() -> None:
    config = {"base_url": "http://localhost:50000", "username": "b1", "password": "s3cret"}
    blob = encrypt_config(config)
    assert isinstance(blob, bytes)
    assert b"s3cret" not in blob
    assert decrypt_config(blob) == config


def test_nonce_is_random_per_encryption() -> None:
    config = {"password": "same"}
    assert encrypt_config(config) != encrypt_config(config)


def test_decrypt_rejects_tampered_blob() -> None:
    blob = bytearray(encrypt_config({"password": "s3cret"}))
    blob[-1] ^= 0xFF
    with pytest.raises(CryptoError, match="could not be decrypted"):
        decrypt_config(bytes(blob))


def test_decrypt_empty_blob_is_empty_config() -> None:
    assert decrypt_config(None) == {}
    assert decrypt_config(b"") == {}


def test_bad_env_key_length_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SCM_CREDENTIAL_KEY", base64.b64encode(b"short").decode())
    with pytest.raises(CryptoError, match="32 bytes"):
        encrypt_config({"password": "x"})


def test_secret_key_detection() -> None:
    for key in ("password", "api_key", "client_secret", "refresh_token", "passphrase"):
        assert is_secret_key(key) is True
    for key in ("base_url", "username", "organization_id", "schedule"):
        assert is_secret_key(key) is False


def test_mask_config_hides_only_secrets() -> None:
    config = {
        "base_url": "http://localhost:50000",
        "username": "b1user",
        "password": "s3cret",
        "api_key": "abc",
        "refresh_token": "",
    }
    masked = mask_config(config)
    assert masked["base_url"] == "http://localhost:50000"
    assert masked["username"] == "b1user"
    assert masked["password"] == "***"
    assert masked["api_key"] == "***"
    assert masked["refresh_token"] == ""  # empty stays empty, not a fake secret
    assert "s3cret" not in str(masked)
    assert "abc" not in str(masked)
