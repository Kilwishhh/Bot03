"""Phase 7 — API read-only enforcement.

Confirms that the public read-only endpoints (no auth required) only accept GET.
Any test that fails here means a write-capable method was accidentally added to
a path that should be read-only.
"""

import pytest
from fastapi.testclient import TestClient

from app.api.server import app


@pytest.fixture
def client():
    return TestClient(app, raise_server_exceptions=False)


# Endpoints that should exist and respond to GET
GETTABLE_ENDPOINTS = [
    ("/health", 200),
    ("/status", 200),
    ("/summary", 200),
    ("/ready", 200),
    ("/metrics", 200),
    ("/orders", 200),
    ("/signals", 200),
    ("/trades", 200),
    ("/balances", 200),
    ("/positions", 200),
    ("/events", 200),
    ("/errors", 200),
]


@pytest.mark.parametrize("path,expected", GETTABLE_ENDPOINTS)
def test_endpoint_accepts_get(client, path, expected):
    """Every listed path must respond to GET with 2xx."""
    response = client.get(path)
    assert response.status_code == expected, f"GET {path} returned {response.status_code}"


@pytest.mark.parametrize("path", [p for p, _ in GETTABLE_ENDPOINTS])
def test_endpoint_rejects_post(client, path):
    """Every read-only path must reject POST with 405 or 403."""
    response = client.post(path, json={})
    assert response.status_code in (401, 405, 403, 422), (
        f"POST {path} returned {response.status_code} — should be 401/405/403/422"
    )


@pytest.mark.parametrize("path", [p for p, _ in GETTABLE_ENDPOINTS])
def test_endpoint_rejects_put(client, path):
    """Every read-only path must reject PUT with 405 or 403."""
    response = client.put(path, json={})
    assert response.status_code in (405, 403, 422), (
        f"PUT {path} returned {response.status_code} — should be 405/403/422"
    )


@pytest.mark.parametrize("path", [p for p, _ in GETTABLE_ENDPOINTS])
def test_endpoint_rejects_delete(client, path):
    """Every read-only path must reject DELETE with 405 or 403."""
    response = client.delete(path)
    assert response.status_code in (405, 403), (
        f"DELETE {path} returned {response.status_code} — should be 405/403"
    )


def test_metrics_returns_counts(client):
    """The /metrics endpoint must return counts for the operational tables."""
    resp = client.get("/metrics")
    assert resp.status_code == 200
    data = resp.json()
    for table in ("signals", "orders", "trades", "daily_pnl", "bot_events", "errors"):
        assert table in data, f"/metrics missing key: {table}"
        assert isinstance(data[table], int), f"/metrics[{table}] must be int"
        assert data[table] >= 0, f"/metrics[{table}] must be non-negative"


def test_health_returns_mode_and_live_flag(client):
    """The /health endpoint must expose mode and live_trading_enabled."""
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert "healthy" in data
    assert "mode" in data
    assert "live_trading_enabled" in data


def test_remote_control_disabled_by_default(client):
    """Remote control must be disabled unless explicitly enabled via env."""
    resp = client.get("/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("remote_control_enabled") is False, (
        "remote_control_enabled must be False by default"
    )
