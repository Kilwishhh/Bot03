"""Password hashing + session token management for multi-user auth.

Uses PBKDF2 (stdlib, no extra deps) for hashing. Session tokens are 32 random
bytes hex-encoded; the database stores the raw token as the row PK so it acts
as a bearer credential.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from datetime import UTC, datetime, timedelta

_PBKDF2_ITERATIONS = 200_000
_PBKDF2_ALGO = "sha256"
_SALT_BYTES = 16


def hash_password(password: str) -> str:
    """Return a self-describing hash string: `pbkdf2_sha256$iters$salt_hex$hash_hex`."""
    if not password:
        raise ValueError("password must be non-empty")
    salt = secrets.token_bytes(_SALT_BYTES)
    digest = hashlib.pbkdf2_hmac(_PBKDF2_ALGO, password.encode("utf-8"), salt, _PBKDF2_ITERATIONS)
    return f"pbkdf2_{_PBKDF2_ALGO}${_PBKDF2_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    """Constant-time comparison against a stored hash string."""
    try:
        algo, iters_s, salt_hex, hash_hex = stored.split("$", 3)
    except ValueError:
        return False
    if not algo.startswith("pbkdf2_"):
        return False
    algo_name = algo.split("_", 1)[1]
    try:
        iters = int(iters_s)
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(hash_hex)
    except (ValueError, TypeError):
        return False
    actual = hashlib.pbkdf2_hmac(algo_name, password.encode("utf-8"), salt, iters)
    return hmac.compare_digest(actual, expected)


def generate_session_token() -> str:
    """Return a new opaque session token (32 random bytes hex)."""
    return secrets.token_hex(32)


def default_session_ttl() -> timedelta:
    days = int(os.environ.get("ERMIS_SESSION_TTL_DAYS", "7"))
    return timedelta(days=max(1, days))


def expires_at_from_now(ttl: timedelta | None = None) -> datetime:
    return datetime.now(UTC) + (ttl or default_session_ttl())
