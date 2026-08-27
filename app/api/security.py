"""Security middleware: rate limiting, security headers, HTTPS enforcement, audit log.

All components are designed to be lightweight, dependency-free, and safe to
import even when the API is not running (so the rest of the app keeps working).
"""

from __future__ import annotations

import json
import logging
import time
from collections import deque
from collections.abc import Callable
from pathlib import Path
from typing import Any

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.config import Settings

logger = logging.getLogger(__name__)


# ----------------------------------------------------------------------
# Security headers
# ----------------------------------------------------------------------

_DEFAULT_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
}


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Attach defensive HTTP headers to every response."""

    async def dispatch(self, request: Request, call_next: Callable[..., Any]) -> Response:
        response = await call_next(request)
        for header, value in _DEFAULT_SECURITY_HEADERS.items():
            response.headers.setdefault(header, value)
        return response


# ----------------------------------------------------------------------
# HTTPS enforcement
# ----------------------------------------------------------------------

class HTTPSEnforcementMiddleware(BaseHTTPMiddleware):
    """Reject plain-HTTP requests when ``api_require_https`` is True.

    Two signals count as HTTPS:
      1. The URL scheme is https (``request.url.scheme == 'https'``)
      2. A reverse proxy forwarded the request with ``X-Forwarded-Proto: https``
    """

    def __init__(self, app: Any, require_https: bool) -> None:
        super().__init__(app)
        self._require_https = require_https

    async def dispatch(self, request: Request, call_next: Callable[..., Any]) -> Response:
        if not self._require_https:
            return await call_next(request)
        if request.url.scheme == "https":
            return await call_next(request)
        forwarded = request.headers.get("x-forwarded-proto", "").lower().strip()
        if forwarded == "https":
            return await call_next(request)
        return JSONResponse(
            status_code=400,
            content={"detail": "HTTPS required; set api_require_https=false in dev or use TLS"},
        )


# ----------------------------------------------------------------------
# Rate limiting (in-memory, per-IP, sliding window)
# ----------------------------------------------------------------------

class _SlidingWindowLimiter:
    """A tiny in-process token-bucket-style limiter.

    One instance is created at app startup. State is held in memory; this is
    good enough to protect a single-instance deployment from accidental
    tight-loop hammering, but it is not distributed. If the app is scaled
    horizontally, swap this for a Redis-backed limiter.
    """

    def __init__(self, per_minute: int) -> None:
        self._per_minute = max(per_minute, 1)
        self._buckets: dict[str, deque[float]] = {}
        self._last_prune = time.monotonic()

    def check(self, key: str) -> tuple[bool, int]:
        """Return ``(allowed, retry_after_seconds)``."""
        now = time.monotonic()
        # opportunistic prune to keep the dict small
        if now - self._last_prune > 60:
            self._last_prune = now
            cutoff = now - 60
            for k in list(self._buckets):
                bucket = self._buckets[k]
                while bucket and bucket[0] < cutoff:
                    bucket.popleft()
                if not bucket:
                    self._buckets.pop(k, None)
        bucket = self._buckets.setdefault(key, deque())
        cutoff = now - 60
        while bucket and bucket[0] < cutoff:
            bucket.popleft()
        if len(bucket) >= self._per_minute:
            retry_after = max(1, int(60 - (now - bucket[0])))
            return False, retry_after
        bucket.append(now)
        return True, 0


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Per-IP sliding-window rate limit."""

    def __init__(self, app: Any, per_minute: int) -> None:
        super().__init__(app)
        self._limiter = _SlidingWindowLimiter(per_minute)
        # Endpoints exempt from rate limiting (read-only health and metrics).
        self._exempt = ("/health", "/status", "/metrics", "/docs", "/openapi.json", "/redoc")

    async def dispatch(self, request: Request, call_next: Callable[..., Any]) -> Response:
        path = request.url.path
        for prefix in self._exempt:
            if path == prefix or path.startswith(prefix + "/"):
                return await call_next(request)
        client_ip = (
            request.client.host if request.client else "unknown"
        )
        # honour X-Forwarded-For when behind a trusted reverse proxy
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            client_ip = forwarded.split(",")[0].strip() or client_ip
        allowed, retry_after = self._limiter.check(client_ip)
        if not allowed:
            logger.warning("rate limit exceeded for %s on %s", client_ip, path)
            return JSONResponse(
                status_code=429,
                content={"detail": f"rate limit exceeded; retry in {retry_after}s"},
                headers={"Retry-After": str(retry_after)},
            )
        return await call_next(request)


# ----------------------------------------------------------------------
# Audit log
# ----------------------------------------------------------------------

class AuditLogger:
    """Append-only JSONL audit log of privileged operations.

    Written to ``<api_audit_log_dir>/audit.log`` (defaults to ``./audit``).
    Each line is a single JSON object with ``ts``, ``actor``, ``action``,
    ``detail``, and ``result``. Designed to be tail-friendly and to ingest
    into any log aggregator without modification.
    """

    def __init__(self, path: Path) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def record(self, *, actor: str, action: str, detail: dict[str, Any], result: str) -> None:
        try:
            entry = {
                "ts": int(time.time()),
                "actor": actor,
                "action": action,
                "detail": detail,
                "result": result,
            }
            with self._path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry, default=str) + "\n")
        except Exception as exc:  # noqa: BLE001 — audit must never crash the app
            logger.error("failed to write audit log entry: %s", exc)

    def tail(self, limit: int = 50) -> list[dict[str, Any]]:
        if not self._path.exists():
            return []
        try:
            with self._path.open("r", encoding="utf-8") as fh:
                lines = fh.readlines()[-limit:]
            return [json.loads(line) for line in lines if line.strip()]
        except Exception as exc:  # noqa: BLE001
            logger.error("failed to read audit log: %s", exc)
            return []


_audit_logger: AuditLogger | None = None


def get_audit_logger() -> AuditLogger:
    """Return the process-wide audit logger (lazily created)."""
    global _audit_logger
    if _audit_logger is None:
        settings = Settings()
        log_dir = Path(getattr(settings, "api_audit_log_dir", "./audit"))
        _audit_logger = AuditLogger(log_dir / "audit.log")
    return _audit_logger



