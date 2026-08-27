"""Tests for security middleware and audit log."""

import time

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.security import (
    AuditLogger,
    HTTPSEnforcementMiddleware,
    RateLimitMiddleware,
    SecurityHeadersMiddleware,
    _SlidingWindowLimiter,
)

# ----------------------------------------------------------------------
# SecurityHeadersMiddleware
# ----------------------------------------------------------------------

def test_security_headers_attached():
    from fastapi import Request
    app = FastAPI()
    app.add_middleware(SecurityHeadersMiddleware)

    @app.get("/ok")
    def ok(_: Request):
        return {"ok": True}

    client = TestClient(app)
    response = client.get("/ok")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "no-referrer"


# ----------------------------------------------------------------------
# HTTPSEnforcementMiddleware
# ----------------------------------------------------------------------

def test_https_enforcement_off_allows_http():
    from fastapi import Request
    app = FastAPI()
    app.add_middleware(HTTPSEnforcementMiddleware, require_https=False)

    @app.get("/ok")
    def ok(_: Request):
        return {"ok": True}

    client = TestClient(app)
    assert client.get("http://localhost/ok").status_code == 200


def test_https_enforcement_on_blocks_plain_http():
    from fastapi import Request
    app = FastAPI()
    app.add_middleware(HTTPSEnforcementMiddleware, require_https=True)

    @app.get("/ok")
    def ok(_: Request):
        return {"ok": True}

    client = TestClient(app)
    response = client.get("http://localhost/ok")
    assert response.status_code == 400
    assert "HTTPS required" in response.json()["detail"]


def test_https_enforcement_on_allows_forwarded_proto():
    from fastapi import Request
    app = FastAPI()
    app.add_middleware(HTTPSEnforcementMiddleware, require_https=True)

    @app.get("/ok")
    def ok(_: Request):
        return {"ok": True}

    client = TestClient(app)
    response = client.get("http://localhost/ok", headers={"x-forwarded-proto": "https"})
    assert response.status_code == 200


# ----------------------------------------------------------------------
# RateLimitMiddleware / SlidingWindowLimiter
# ----------------------------------------------------------------------

def test_rate_limit_allows_under_limit():
    limiter = _SlidingWindowLimiter(per_minute=10)
    for _ in range(9):
        allowed, _ = limiter.check("ip1")
        assert allowed is True


def test_rate_limit_blocks_over_limit():
    limiter = _SlidingWindowLimiter(per_minute=3)
    for _ in range(3):
        allowed, _ = limiter.check("ip1")
        assert allowed is True
    allowed, retry_after = limiter.check("ip1")
    assert allowed is False
    assert retry_after >= 1


def test_rate_limit_per_key_isolation():
    limiter = _SlidingWindowLimiter(per_minute=2)
    for _ in range(2):
        limiter.check("ip1")
    # ip1 should be blocked
    assert limiter.check("ip1")[0] is False
    # ip2 should still pass
    assert limiter.check("ip2")[0] is True


def test_rate_limit_middleware_exempts_health():
    from fastapi import Request
    app = FastAPI()
    app.add_middleware(RateLimitMiddleware, per_minute=1)

    @app.get("/health")
    def health(_: Request):
        return {"ok": True}

    client = TestClient(app)
    for _ in range(5):
        assert client.get("/health").status_code == 200


def test_rate_limit_middleware_blocks_non_health():
    from fastapi import Request
    app = FastAPI()
    app.add_middleware(RateLimitMiddleware, per_minute=1)

    @app.get("/data")
    def data(_: Request):
        return {"ok": True}

    client = TestClient(app)
    r1 = client.get("/data")
    assert r1.status_code == 200
    r2 = client.get("/data")
    assert r2.status_code == 429
    assert "Retry-After" in r2.headers


def test_rate_limit_honours_forwarded_for():
    from fastapi import Request
    app = FastAPI()
    app.add_middleware(RateLimitMiddleware, per_minute=1)

    @app.get("/data")
    def data(_: Request):
        return {"ok": True}

    client = TestClient(app)
    # Hammer the same forwarded IP twice — should be blocked on the second call
    r1 = client.get("/data", headers={"x-forwarded-for": "10.0.0.42"})
    assert r1.status_code == 200
    r2 = client.get("/data", headers={"x-forwarded-for": "10.0.0.42"})
    assert r2.status_code == 429
    # A different forwarded IP should still have its own bucket
    r3 = client.get("/data", headers={"x-forwarded-for": "10.0.0.99"})
    assert r3.status_code == 200


# ----------------------------------------------------------------------
# AuditLogger
# ----------------------------------------------------------------------

def test_audit_logger_writes_jsonl(tmp_path):
    log_file = tmp_path / "audit.log"
    logger = AuditLogger(log_file)

    logger.record(actor="127.0.0.1", action="test.action", detail={"k": "v"}, result="ok")

    lines = log_file.read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) == 1
    import json
    entry = json.loads(lines[0])
    assert entry["actor"] == "127.0.0.1"
    assert entry["action"] == "test.action"
    assert entry["detail"] == {"k": "v"}
    assert entry["result"] == "ok"
    assert "ts" in entry


def test_audit_logger_tail_returns_newest_last(tmp_path):
    log_file = tmp_path / "audit.log"
    logger = AuditLogger(log_file)
    for i in range(5):
        logger.record(actor="ip", action=f"action.{i}", detail={}, result="ok")
        time.sleep(0.001)

    entries = logger.tail(limit=5)
    assert len(entries) == 5
    # tail returns the last N lines in file order (oldest -> newest within window)
    assert entries[0]["action"] == "action.0"
    assert entries[-1]["action"] == "action.4"


def test_audit_logger_tail_respects_limit(tmp_path):
    logger = AuditLogger(tmp_path / "audit.log")
    for i in range(10):
        logger.record(actor="ip", action=f"a.{i}", detail={}, result="ok")
        time.sleep(0.001)

    assert len(logger.tail(limit=5)) == 5


def test_audit_logger_tail_empty_when_no_file(tmp_path):
    logger = AuditLogger(tmp_path / "does_not_exist.log")
    assert logger.tail() == []


def test_audit_logger_record_never_raises(tmp_path):
    """The audit log must never crash the calling thread."""
    logger = AuditLogger(tmp_path / "audit.log")
    # Even with a read-only parent dir (can't write), record() should not raise
    import os
    os.chmod(tmp_path, 0o444)
    try:
        logger.record(actor="ip", action="a", detail={}, result="ok")  # should not raise
    finally:
        os.chmod(tmp_path, 0o755)


def test_audit_logger_tail_never_raises(tmp_path):
    logger = AuditLogger(tmp_path / "audit.log")
    logger.tail()  # should not raise even if file doesn't exist
    # write a corrupt line
    (tmp_path / "audit.log").write_text("not json {", encoding="utf-8")
    logger.tail()  # should return [] on corrupt data
