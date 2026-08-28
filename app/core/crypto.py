"""Symmetric encryption for secrets at rest.

Uses Fernet (AES-128-CBC + HMAC) with a server-managed key. The key is loaded
from the `ERMIS_SECRET_KEY` env var (44-byte url-safe base64). If unset, a
key is generated and persisted to `.ermis_secret.key` for development.

In production, ERMIS_SECRET_KEY MUST be set to a stable, securely stored value.
"""

from __future__ import annotations

import os
import secrets
from functools import lru_cache
from pathlib import Path


def _load_or_create_key() -> bytes:
    explicit = os.environ.get("ERMIS_SECRET_KEY")
    if explicit:
        return explicit.encode("utf-8")

    key_path = Path(".ermis_secret.key")
    if key_path.exists():
        return key_path.read_bytes().strip()
    key = secrets.token_urlsafe(32)
    key_path.write_bytes(key.encode("utf-8"))
    try:
        key_path.chmod(0o600)
    except OSError:
        pass
    return key.encode("utf-8")


@lru_cache(maxsize=1)
def _cipher():
    from cryptography.fernet import Fernet
    raw = _load_or_create_key()
    # Fernet needs 32 url-safe-base64 bytes (44 chars total)
    import base64, hashlib
    if len(raw) == 44:
        key = raw
    else:
        digest = hashlib.sha256(raw).digest()
        key = base64.urlsafe_b64encode(digest)
    return Fernet(key)


def encrypt(plaintext: str) -> bytes:
    if not plaintext:
        return b""
    return _cipher().encrypt(plaintext.encode("utf-8"))


def decrypt(token: bytes) -> str:
    if not token:
        return ""
    return _cipher().decrypt(bytes(token)).decode("utf-8")


def reset_for_testing() -> None:
    """Clear the cached cipher — used by tests to swap env vars."""
    _cipher.cache_clear()
