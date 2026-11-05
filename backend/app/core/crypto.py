"""Credential encryption at rest (Part N, G1; P4-04).

AES-256-GCM with a 32-byte key that lives outside the database:
SCM_CREDENTIAL_KEY (base64) in production, or a 0600 key file generated on
first use for the dev profile. Configs are stored as a single encrypted blob;
only decrypted in memory for the duration of a connector call.

API responses and audit payloads must go through ``mask_config`` - raw
secrets are never serialized.
"""

from __future__ import annotations

import base64
import json
import os
import secrets
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.config import settings

NONCE_BYTES = 12
_DEV_KEY_PATH = Path("data/keys/credentials.key")

_SECRET_MARKERS = ("password", "secret", "token", "key", "credential", "passphrase")


class CryptoError(RuntimeError):
    """Raised when a credential blob cannot be encrypted or decrypted."""


def _decode_key(raw: str) -> bytes:
    try:
        key = base64.b64decode(raw, validate=True)
    except Exception as exc:  # noqa: BLE001 - normalize to CryptoError
        raise CryptoError("SCM_CREDENTIAL_KEY must be base64") from exc
    if len(key) != 32:
        raise CryptoError("SCM_CREDENTIAL_KEY must decode to 32 bytes")
    return key


def load_key() -> bytes:
    """Return the 32-byte AES key from env or the 0600 key file.

    The key file is created with 0600 permissions when missing (dev profile
    only; production should provide SCM_CREDENTIAL_KEY via the OS keystore).
    """
    env_key = os.environ.get("SCM_CREDENTIAL_KEY", "")
    if env_key:
        return _decode_key(env_key)

    path = Path(settings.credential_key_file) if settings.credential_key_file else _DEV_KEY_PATH
    if path.exists():
        return _decode_key(path.read_text(encoding="utf-8").strip())

    path.parent.mkdir(parents=True, exist_ok=True)
    key = secrets.token_bytes(32)
    path.write_text(base64.b64encode(key).decode("ascii"), encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:  # pragma: no cover - Windows may not support chmod fully
        pass
    return key


def encrypt_config(config: dict[str, Any]) -> bytes:
    """Encrypt a connector config dict to nonce||ciphertext bytes."""
    key = load_key()
    nonce = secrets.token_bytes(NONCE_BYTES)
    plaintext = json.dumps(config, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return nonce + AESGCM(key).encrypt(nonce, plaintext, b"scm-connector")


def decrypt_config(blob: bytes | None) -> dict[str, Any]:
    """Decrypt a connector config blob; empty blob means no config."""
    if not blob:
        return {}
    key = load_key()
    nonce, ciphertext = blob[:NONCE_BYTES], blob[NONCE_BYTES:]
    try:
        plaintext = AESGCM(key).decrypt(nonce, ciphertext, b"scm-connector")
    except Exception as exc:  # noqa: BLE001
        raise CryptoError("connector config could not be decrypted") from exc
    data = json.loads(plaintext.decode("utf-8"))
    if not isinstance(data, dict):
        raise CryptoError("connector config must be a JSON object")
    return data


def is_secret_key(key: str) -> bool:
    """True when a config key name looks credential-bearing."""
    lowered = key.lower()
    return any(marker in lowered for marker in _SECRET_MARKERS)


def mask_config(config: dict[str, Any]) -> dict[str, Any]:
    """Return a copy safe to serialize: secret-looking values become '***'.

    Non-secret values pass through unchanged so the UI can still show the
    endpoint/username/etc. Numbers and booleans are never secrets.
    """
    masked: dict[str, Any] = {}
    for key, value in config.items():
        if is_secret_key(str(key)) and value not in (None, ""):
            masked[key] = "***"
        else:
            masked[key] = value
    return masked
