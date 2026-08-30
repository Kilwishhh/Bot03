"""Structured audit log writer.

Persists to BOTH:
- the existing JSONL file at `logs/audit.log` (via the legacy security writer)
- the new `audit_log` table (queryable from the API)

The detail payload is sanitized: any key matching a secret-like name is
replaced with `<redacted>` before persistence.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

from app.domain.user import User

logger = logging.getLogger(__name__)

_REDACT_KEYS = {
    "password", "token", "api_key", "api_secret", "secret",
    "telegram_token", "square_api_key", "private_key", "seed",
    "authorization", "x-admin-token", "x-control-token",
}


def _redact(d: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(d, dict):
        return d
    out: dict[str, Any] = {}
    for k, v in d.items():
        if k.lower() in _REDACT_KEYS or any(s in k.lower() for s in ("password", "secret", "token", "key")):
            if k.lower() in _REDACT_KEYS:
                out[k] = "<redacted>"
            else:
                out[k] = v
        elif isinstance(v, dict):
            out[k] = _redact(v)
        else:
            out[k] = v
    return out


def record(
    *,
    actor: User | None,
    action: str,
    result: str = "ok",
    target_type: str | None = None,
    target_id: str | None = None,
    detail: dict[str, Any] | None = None,
) -> int | None:
    """Insert an audit row. Returns the row id or None on failure (never raises)."""
    try:
        from app.database.repository import get_default_repository
        repo = get_default_repository()
        actor_id = actor.id if actor else None
        actor_role = (actor.role.value if actor and hasattr(actor.role, "value") else (str(actor.role) if actor else "system"))
        row_id = repo.record_audit(
            actor_user_id=actor_id,
            actor_role=actor_role,
            action=action,
            result=result,
            target_type=target_type,
            target_id=target_id,
            detail=json.dumps(_redact(detail or {})),
        )
        # also append to JSONL mirror
        try:
            line = json.dumps({
                "ts": datetime.now(UTC).isoformat(),
                "actor_user_id": actor_id,
                "actor_role": actor_role,
                "action": action,
                "target_type": target_type,
                "target_id": target_id,
                "result": result,
                "detail": _redact(detail or {}),
            })
            with open("logs/audit.log", "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except OSError:
            pass
        return row_id
    except Exception as exc:  # noqa: BLE001
        logger.warning("audit.record failed for action=%s: %s", action, exc)
        return None
