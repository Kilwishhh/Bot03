"""Timeframe system end-to-end tests.

Validates:
- get_timeframe_minutes parsing all valid formats
- is_valid_timeframe rejects invalid inputs
- candle aggregation for non-native intervals
- API accepts any valid timeframe string (7m, 10m, 20m, 45m, 90m, 2h, etc.)
- persistence: PATCH → GET returns the saved timeframe
- existing 15m strategies still work (default fallback)
"""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.strategy.indicators import get_timeframe_minutes
from app.strategy.condition_engine import is_valid_timeframe
from app.strategy.scanner import _aggregate_candles, _get_candles_for_timeframe
from app.exchange.models import Candle


# ── Unit helpers ──────────────────────────────────────────────────────────────

class FakeCandleStore:
    """Returns deterministic 1m candles for testing aggregation."""
    def __init__(self, count: int = 60):
        self._default_count = count

    def candles(self, symbol: str, timeframe: str, limit: int = 200) -> list[Candle]:
        n = min(self._default_count, limit)
        t0 = datetime(2026, 9, 2, 12, 0, 0, tzinfo=UTC)
        out = []
        for i in range(n):
            t = datetime.fromtimestamp(t0.timestamp() + i * 60, tz=UTC)
            out.append(Candle(
                open_time=t,
                close_time=datetime.fromtimestamp(t.timestamp() + 59, tz=UTC),
                open=100.0 + i * 0.5,
                high=101.0 + i * 0.5,
                low=99.0 + i * 0.5,
                close=100.5 + i * 0.5,
                volume=10.0 + i,
            ))
        return out


# ── get_timeframe_minutes ──────────────────────────────────────────────────────

@pytest.mark.parametrize("tf,expected", [
    ("1m",   1),
    ("5m",   5),
    ("7m",   7),
    ("10m",  10),
    ("15m",  15),
    ("20m",  20),
    ("30m",  30),
    ("45m",  45),
    ("90m",  90),
    ("1h",   60),
    ("2h",   120),
    ("4h",   240),
    ("6h",   360),
    ("8h",   480),
    ("12h",  720),
    ("1d",   1440),
    ("3d",   4320),
])
def test_get_timeframe_minutes(tf: str, expected: int):
    assert get_timeframe_minutes(tf) == expected


def test_get_timeframe_minutes_unknown():
    with pytest.raises(ValueError):
        get_timeframe_minutes("invalid")


# ── is_valid_timeframe ─────────────────────────────────────────────────────────

@pytest.mark.parametrize("valid", [
    "1m", "5m", "7m", "10m", "15m", "20m", "30m", "45m", "90m",
    "1h", "2h", "4h", "6h", "8h", "12h", "1d", "3d", "1w", "1M",
])
def test_is_valid_timeframe_valid(valid: str):
    assert is_valid_timeframe(valid) is True


@pytest.mark.parametrize("invalid", [
    "", "0m", "-5m", "abc", "15", "m", "h", "1", "1x",
    "00m", "1.5m",
])
def test_is_valid_timeframe_invalid(invalid: str):
    assert is_valid_timeframe(invalid) is False


# ── Candle aggregation ──────────────────────────────────────────────────────────

def test_aggregate_candles_7m():
    """60 × 1m candles → 9 × 7m candles (8 full buckets + 1 partial of 4)."""
    store = FakeCandleStore(60)
    result = _get_candles_for_timeframe(store, "BTCUSDT", "7m", 60)
    assert len(result) == 9  # 60 / 7 = 8 full + 1 partial of 4
    # Bucket 0: candles 0-6. open=candle[0].open=100.0, close=candle[6].close=103.5
    assert result[0].open == 100.0
    assert result[0].close == pytest.approx(100.5 + 6 * 0.5)  # 103.5
    # High = max of candles 0-6 → max(101.0+i*0.5) = 101.0+6*0.5 = 104.0
    assert result[0].high == pytest.approx(101.0 + 6 * 0.5)  # 104.0
    # Low = min of candles 0-6 → min(99.0+i*0.5) = 99.0 (candle 0)
    assert result[0].low == pytest.approx(99.0)


def test_aggregate_candles_15m():
    """15m is native Binance — store returns raw 1m candles directly."""
    store = FakeCandleStore(60)
    result = _get_candles_for_timeframe(store, "BTCUSDT", "15m", 60)
    # Native timeframe bypasses aggregation; store returns 60 1m candles
    assert len(result) == 60
    assert result[0].open == 100.0
    assert result[0].close == pytest.approx(100.5)


def test_aggregate_candles_native_1m():
    """Native 1m — no aggregation, raw candles returned."""
    store = FakeCandleStore(30)
    result = _get_candles_for_timeframe(store, "BTCUSDT", "1m", 30)
    assert len(result) == 30
    assert result[0].open == 100.0


def test_aggregate_candles_native_2h():
    """Native 2h — no aggregation."""
    store = FakeCandleStore(30)
    result = _get_candles_for_timeframe(store, "BTCUSDT", "2h", 30)
    assert len(result) == 30


def test_aggregate_candles_2h_custom():
    """20m is a custom interval aggregated from 1m: 60 1m candles → 3 buckets of 20m."""
    store = FakeCandleStore(60)
    result = _get_candles_for_timeframe(store, "BTCUSDT", "20m", 60)
    # 60 / 20 = 3 full buckets
    assert len(result) == 3
    assert result[0].open == 100.0
    # Bucket 0: candles 0-19. close=candle[19].close=100.5+19*0.5=110.0
    assert result[0].close == pytest.approx(100.5 + 19 * 0.5)  # 110.0


def test_aggregate_candles_90m_custom():
    """Custom 90m aggregated from 1m: 270 candles → 3 buckets (limit=200 still covers all 270)."""
    store = FakeCandleStore(270)
    result = _get_candles_for_timeframe(store, "BTCUSDT", "90m", 200)
    # Store ignores limit and returns 270 1m candles → 270/90 = 3 buckets
    assert len(result) == 3


# ── API integration ─────────────────────────────────────────────────────────────

def test_admin_create_strategy_with_custom_timeframe(client):
    """POST /admin/strategies accepts 7m, 10m, 90m, 2h and persists them."""
    token = "test-admin-secret-token-12345"
    headers = {"X-Admin-Token": token, "Content-Type": "application/json"}

    for tf in ("7m", "10m", "20m", "45m", "90m", "2h", "1d"):
        body = {
            "name": f"Test {tf}",
            "market": "binance_futures",
            "timeframe": tf,
            "execution_mode": "paper",
        }
        resp = client.post("/admin/strategies", headers=headers, json=body)
        assert resp.status_code == 200, f"Failed for {tf}: {resp.json()}"
        sid = resp.json()["id"]

        # GET must return the saved timeframe
        get_resp = client.get(f"/admin/strategies/{sid}", headers={"X-Admin-Token": token})
        assert get_resp.status_code == 200
        assert get_resp.json()["timeframe"] == tf, f"GET mismatch for {tf}"


def test_admin_patch_timeframe(client):
    """PATCH changes timeframe; GET confirms the new value."""
    token = "test-admin-secret-token-12345"
    headers = {"X-Admin-Token": token, "Content-Type": "application/json"}

    # Create with default 15m
    body = {"name": "TF Patch Test", "market": "binance_futures", "execution_mode": "paper"}
    resp = client.post("/admin/strategies", headers=headers, json=body)
    sid = resp.json()["id"]

    # Patch to 7m
    patch = client.patch(f"/admin/strategies/{sid}", headers=headers, json={"timeframe": "7m"})
    assert patch.status_code == 200, patch.json()

    # GET must show 7m
    get_ = client.get(f"/admin/strategies/{sid}", headers={"X-Admin-Token": token})
    assert get_.json()["timeframe"] == "7m"

    # Patch to 2h
    patch2 = client.patch(f"/admin/strategies/{sid}", headers=headers, json={"timeframe": "2h"})
    assert patch2.status_code == 200
    assert client.get(f"/admin/strategies/{sid}", headers={"X-Admin-Token": token}).json()["timeframe"] == "2h"


def test_admin_rejects_invalid_timeframe(client):
    """PATCH/POST with invalid timeframe returns 400."""
    token = "test-admin-secret-token-12345"
    headers = {"X-Admin-Token": token, "Content-Type": "application/json"}

    body = {"name": "Bad TF", "market": "binance_futures", "execution_mode": "paper"}

    # POST with bad timeframe
    resp = client.post("/admin/strategies", headers=headers, json={**body, "timeframe": "0m"})
    assert resp.status_code == 400

    # Create valid, then patch invalid
    sid = client.post("/admin/strategies", headers=headers, json=body).json()["id"]
    bad = client.patch(f"/admin/strategies/{sid}", headers=headers, json={"timeframe": "-5m"})
    assert bad.status_code == 400


def test_list_strategies_includes_timeframe(client):
    """GET /admin/strategies list returns timeframe for each strategy."""
    token = "test-admin-secret-token-12345"
    headers = {"X-Admin-Token": token, "Content-Type": "application/json"}

    for tf in ("7m", "2h", "1d"):
        client.post("/admin/strategies", headers=headers, json={
            "name": f"List {tf}", "market": "binance_futures",
            "timeframe": tf, "execution_mode": "paper",
        })

    list_resp = client.get("/admin/strategies", headers={"X-Admin-Token": token})
    assert list_resp.status_code == 200
    strats = list_resp.json()
    tfs = {s["name"]: s["timeframe"] for s in strats}
    assert tfs.get("List 7m") == "7m"
    assert tfs.get("List 2h") == "2h"
    assert tfs.get("List 1d") == "1d"


def test_existing_15m_strategy_unchanged(client):
    """A strategy created with no explicit timeframe defaults to 15m."""
    token = "test-admin-secret-token-12345"
    headers = {"X-Admin-Token": token, "Content-Type": "application/json"}

    resp = client.post("/admin/strategies", headers=headers, json={
        "name": "No TF Specified", "market": "binance_futures", "execution_mode": "paper",
    })
    sid = resp.json()["id"]
    get_ = client.get(f"/admin/strategies/{sid}", headers={"X-Admin-Token": token})
    assert get_.json()["timeframe"] == "15m"
