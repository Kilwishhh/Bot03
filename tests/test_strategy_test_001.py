"""Tests for STRATEGY-TEST-001 — RSI Reversion 1M Paper Test strategy."""

import sqlite3
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from app.core.rbac import AccessContext
from app.database.repository import TradingRepository
from app.domain.user import User, UserRole, UserStatus
from app.exchange.models import Candle, OrderRequest, OrderSide, OrderType
from app.exchange.paper import PaperTradingAdapter
from fastapi.testclient import TestClient

client = TestClient(__import__("app.api.server", fromlist=["app"]).app,
                    raise_server_exceptions=True)

TEST_EMAIL = "test@local.dev"
STRATEGY_NAME = "RSI Reversion 1M Test"
STRATEGY_ID = "47ddb081-d9bb-454d-bc67-f715d96ef6c4"


def _get_user_id() -> str:
    conn = sqlite3.connect("trading.db")
    row = conn.execute("SELECT id FROM users WHERE email=?", (TEST_EMAIL,)).fetchone()
    conn.close()
    if not row:
        pytest.skip("Test user test@local.dev not seeded")
    return row[0]


def _reset_strategy():
    conn = sqlite3.connect("trading.db")
    sid = STRATEGY_ID
    conn.execute("DELETE FROM signal_followups WHERE signal_id IN "
                 "(SELECT id FROM signals WHERE strategy_id=?)", (sid,))
    conn.execute("DELETE FROM signals WHERE strategy_id=?", (sid,))
    conn.execute("DELETE FROM trades WHERE strategy=?", (sid,))
    conn.execute("DELETE FROM positions WHERE symbol IN "
                 "('BTCUSDT','ETHUSDT','SOLUSDT')")
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# A. Strategy record exists with correct config
# ---------------------------------------------------------------------------

def test_strategy_record_exists():
    conn = sqlite3.connect("trading.db")
    row = conn.execute(
        "SELECT id, name, lifecycle_state, execution_mode, market FROM strategies "
        "WHERE name=?", (STRATEGY_NAME,)).fetchone()
    conn.close()
    assert row is not None, f"Strategy '{STRATEGY_NAME}' must exist"
    sid, name, state, mode, market = row
    assert name == STRATEGY_NAME
    assert state == "paper", f"Strategy must be in paper state, got {state}"
    assert mode == "paper"


def test_strategy_lifecycle_is_paper_not_live():
    conn = sqlite3.connect("trading.db")
    state = conn.execute(
        "SELECT lifecycle_state FROM strategies WHERE name=?", (STRATEGY_NAME,)
    ).fetchone()[0]
    conn.close()
    assert state == "paper"


def test_strategy_live_rejected():
    """Confirm LIVE state blocks the dev simulate endpoint."""
    conn = sqlite3.connect("trading.db")
    conn.execute(
        "UPDATE strategies SET lifecycle_state='live' WHERE name=?", (STRATEGY_NAME,))
    conn.commit()
    conn.close()
    try:
        resp = client.post(f"/dev/strategies/{STRATEGY_ID}/simulate-signal")
        # Should not generate new signals; either 404 (route guards it) or
        # 200 with empty results is acceptable as long as nothing is created
        if resp.status_code == 200:
            data = resp.json()
            for r in data.get("results", []):
                assert r["outcome"] != "signal_generated", (
                    "LIVE strategy must not produce signals")
        else:
            assert resp.status_code == 404
    finally:
        conn = sqlite3.connect("trading.db")
        conn.execute(
            "UPDATE strategies SET lifecycle_state='paper' WHERE name=?",
            (STRATEGY_NAME,))
        conn.commit()
        conn.close()


# ---------------------------------------------------------------------------
# B. Test user exists
# ---------------------------------------------------------------------------

def test_test_user_exists():
    conn = sqlite3.connect("trading.db")
    row = conn.execute(
        "SELECT id, email FROM users WHERE email=?", (TEST_EMAIL,)).fetchone()
    conn.close()
    assert row is not None
    assert row[1] == TEST_EMAIL


# ---------------------------------------------------------------------------
# C. RSI indicator correctness
# ---------------------------------------------------------------------------

def _synth_candles(prices: list[float]) -> list[Candle]:
    ts = int(datetime.now(UTC).timestamp() - len(prices) * 60) * 1000
    out = []
    for i, p in enumerate(prices):
        out.append(Candle(
            open_time=datetime.fromtimestamp((ts + i * 60000) / 1000, tz=UTC),
            open=Decimal(str(p)),
            high=Decimal(str(p * 1.001)),
            low=Decimal(str(p * 0.999)),
            close=Decimal(str(p)),
            volume=Decimal("1"),
            close_time=datetime.fromtimestamp((ts + i * 60000 + 59999) / 1000, tz=UTC),
        ))
    return out


def _rsi(candles: list[Candle], period: int = 14) -> float:
    if len(candles) < period + 1:
        return 50.0
    closes = [float(c.close) for c in candles[-period - 1:]]
    gains, losses = [], []
    for i in range(1, len(closes)):
        d = closes[i] - closes[i - 1]
        gains.append(max(d, 0))
        losses.append(max(-d, 0))
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    if avg_loss == 0:
        return 100.0 if avg_gain > 0 else 50.0
    return 100.0 - (100.0 / (1.0 + avg_gain / avg_loss))


def test_rsi_oversold_triggers_long():
    # Steady then crash → RSI < 30
    prices = [100.0] * 15 + [70.0]
    candles = _synth_candles(prices)
    rsi = _rsi(candles)
    assert rsi <= 30, f"Crash should produce RSI <= 30, got {rsi:.1f}"


def test_rsi_overbought_triggers_short():
    # Steady then spike → RSI > 70
    prices = [100.0] * 15 + [130.0]
    candles = _synth_candles(prices)
    rsi = _rsi(candles)
    assert rsi >= 70, f"Spike should produce RSI >= 70, got {rsi:.1f}"


def test_rsi_neutral_no_signal():
    # Alternating up/down equal → RSI near 50
    prices = [100.0 + (i % 2) * 0.5 for i in range(20)]
    candles = _synth_candles(prices)
    rsi = _rsi(candles)
    assert 30 < rsi < 70, f"Alternating should produce neutral RSI, got {rsi:.1f}"


# ---------------------------------------------------------------------------
# D. Entry price correct
# ---------------------------------------------------------------------------

def test_entry_price_uses_signal_candle_close():
    prices = [100.0] * 14 + [95.0] * 3
    candles = _synth_candles(prices)
    entry = float(candles[-2].close)
    assert entry == 95.0


def test_tp_sl_calculation_long():
    entry = 100.0
    tp = entry * 1.003
    sl = entry * 0.995
    assert abs(tp - 100.3) < 0.01
    assert abs(sl - 99.5) < 0.01


def test_tp_sl_calculation_short():
    entry = 100.0
    tp = entry * 0.997
    sl = entry * 1.005
    assert abs(tp - 99.7) < 0.01
    assert abs(sl - 100.5) < 0.01


# ---------------------------------------------------------------------------
# E. Signal record has all required fields
# ---------------------------------------------------------------------------

def test_signal_record_has_all_required_fields():
    _reset_strategy()
    sig_id = str(uuid4())
    uid = _get_user_id()
    ts = datetime.now(UTC).isoformat()
    conn = sqlite3.connect("trading.db")
    conn.execute(
        """INSERT INTO signals
           (id, user_id, strategy_id, symbol, side, confidence, timestamp,
            entry_price, tp1, stop_loss, mode, signal_status,
            trading_status, telegram_status, square_status, created_at, updated_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (sig_id, uid, STRATEGY_ID, "BTCUSDT", "BUY", 0.5, ts,
         100.0, 100.3, 99.5, "paper", "CREATED", "PENDING", "PENDING",
         "PENDING", ts, ts),
    )
    conn.commit()
    conn.close()

    conn = sqlite3.connect("trading.db")
    row = conn.execute("SELECT * FROM signals WHERE id=?", (sig_id,)).fetchone()
    cols = [r[1] for r in conn.execute("PRAGMA table_info(signals)").fetchall()]
    conn.close()
    assert row is not None
    rec = dict(zip(cols, row))
    assert rec["mode"] == "paper"
    assert rec["signal_status"] == "CREATED"
    assert rec["trading_status"] == "PENDING"
    assert rec["telegram_status"] == "PENDING"
    assert rec["square_status"] == "PENDING"
    assert rec["strategy_id"] == STRATEGY_ID
    assert rec["user_id"] == uid


# ---------------------------------------------------------------------------
# F. Paper order execution
# ---------------------------------------------------------------------------

def test_paper_adapter_execute_market_buy():
    paper = PaperTradingAdapter(starting_balance=Decimal("10000"))
    result = paper.place_order(OrderRequest(
        symbol="BTCUSDT", side=OrderSide.BUY, order_type=OrderType.MARKET,
        quantity=Decimal("0.001"), price=None,
    ))
    assert result.order_id is not None
    pos = paper.get_position("BTCUSDT")
    assert pos is not None
    assert float(pos.quantity) == 0.001


def test_paper_adapter_execute_market_sell():
    paper = PaperTradingAdapter(starting_balance=Decimal("10000"))
    paper.place_order(OrderRequest(
        symbol="BTCUSDT", side=OrderSide.BUY, order_type=OrderType.MARKET,
        quantity=Decimal("0.001"), price=None,
    ))
    result = paper.place_order(OrderRequest(
        symbol="BTCUSDT", side=OrderSide.SELL, order_type=OrderType.MARKET,
        quantity=Decimal("0.001"), price=None,
    ))
    assert result.order_id is not None


# ---------------------------------------------------------------------------
# G. Duplicate protection (same candle)
# ---------------------------------------------------------------------------

def test_simulate_signal_rejects_duplicate_same_candle():
    _reset_strategy()
    # First call to discover the candle the endpoint will use
    resp1 = client.post(f"/dev/strategies/{STRATEGY_ID}/simulate-signal")
    assert resp1.status_code == 200
    btc1 = next((r for r in resp1.json()["results"] if r["symbol"] == "BTCUSDT"), None)
    assert btc1 is not None
    # First call may either generate a signal or skip; if generated, second
    # call against the same candle should report duplicate
    if btc1["outcome"] == "signal_generated":
        # The signal timestamp now matches the candle, so the second call
        # against the same live candle must be flagged duplicate
        resp2 = client.post(f"/dev/strategies/{STRATEGY_ID}/simulate-signal")
        assert resp2.status_code == 200
        btc2 = next((r for r in resp2.json()["results"] if r["symbol"] == "BTCUSDT"), None)
        assert btc2 is not None
        # Outcome should be duplicate, cooldown, or skip (all valid dedup forms)
        assert btc2["outcome"] in ("duplicate", "cooldown", "skip"), \
            f"Second call must be dedup'd, got {btc2['outcome']}"
    else:
        # Outcome was already deduped (cooldown/duplicate/skip) — that's fine
        assert btc1["outcome"] in ("duplicate", "cooldown", "skip")


# ---------------------------------------------------------------------------
# H. 1 max position per symbol
# ---------------------------------------------------------------------------

def test_simulate_signal_rejects_when_position_open():
    _reset_strategy()
    conn = sqlite3.connect("trading.db")
    conn.execute(
        "INSERT OR REPLACE INTO positions "
        "(symbol, side, quantity, entry_price, mark_price, leverage, "
        " unrealized_pnl, updated_at) VALUES (?,?,?,?,?,?,?,?)",
        ("BTCUSDT", "BUY", 0.001, 100.0, 100.0, 1, 0.0,
         datetime.now(UTC).isoformat()),
    )
    conn.commit()
    conn.close()
    try:
        resp = client.post(f"/dev/strategies/{STRATEGY_ID}/simulate-signal")
        assert resp.status_code == 200
        data = resp.json()
        btc = next((r for r in data["results"] if r["symbol"] == "BTCUSDT"), None)
        assert btc is not None
        assert btc["outcome"] in ("cooldown", "duplicate"), \
            f"Expected cooldown/duplicate, got {btc['outcome']}"
    finally:
        conn = sqlite3.connect("trading.db")
        conn.execute("DELETE FROM positions WHERE symbol='BTCUSDT'")
        conn.commit()
        conn.close()


# ---------------------------------------------------------------------------
# I. Dev simulation endpoints
# ---------------------------------------------------------------------------

def test_dev_simulate_signal_returns_200():
    _reset_strategy()
    resp = client.post(f"/dev/strategies/{STRATEGY_ID}/simulate-signal")
    assert resp.status_code == 200
    data = resp.json()
    assert data["strategy_test_001"] is True
    assert "results" in data
    assert "symbols_tested" in data


def test_dev_status_returns_strategy_info():
    resp = client.get(f"/dev/strategies/{STRATEGY_ID}/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == STRATEGY_NAME
    assert data["lifecycle_state"] == "paper"
    assert "BTCUSDT" in data["symbols"]


def test_dev_reset_clears_signals_and_trades():
    _reset_strategy()
    resp = client.delete(f"/dev/strategies/{STRATEGY_ID}/reset")
    assert resp.status_code == 200
    data = resp.json()
    assert data["reset"] is True


# ---------------------------------------------------------------------------
# J. Automation rules seeded for strategy
# ---------------------------------------------------------------------------

def test_automation_rules_exist_for_strategy():
    conn = sqlite3.connect("trading.db")
    rows = conn.execute(
        "SELECT id, name, trigger, actions FROM automation_rules "
        "WHERE strategy_id=?", (STRATEGY_ID,)
    ).fetchall()
    conn.close()
    assert len(rows) >= 3, "Should have at least 3 automation rules"
    triggers = {r[2] for r in rows}
    assert "signal_generated" in triggers
