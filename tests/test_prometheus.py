"""Phase 4 — Prometheus /metrics endpoint tests."""

import pytest
from fastapi.testclient import TestClient

from app.api.server import app


@pytest.fixture
def client():
    return TestClient(app, raise_server_exceptions=False)


def test_prometheus_metrics_returns_prometheus_format(client):
    """GET /prom/metrics returns Prometheus text exposition format."""
    resp = client.get("/prom/metrics")
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    assert resp.headers["content-type"].startswith("text/plain")
    body = resp.text
    # Must include the HELP lines for our custom metrics
    assert "mktrader_cycles_total" in body
    assert "mktrader_signals_total" in body
    assert "mktrader_orders_total" in body
    assert "mktrader_errors_total" in body


def test_metrics_endpoint_returns_json_counts(client):
    """GET /metrics returns JSON counts for the legacy API consumers."""
    resp = client.get("/metrics")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, dict)
    for table in ("signals", "orders", "trades", "daily_pnl", "bot_events", "errors"):
        assert table in data, f"missing key: {table}"
        assert isinstance(data[table], int)
