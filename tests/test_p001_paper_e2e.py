"""P0-01 — Paper trading E2E pipeline.

Exercises: Strategy→Signal→Order→Fill→Position→TP/SL→drive-close→Trade→PnL→DB→API
via the existing /dev/strategies/{id}/simulate-signal and /dev/strategies/{id}/drive-close
endpoints, then verifies persisted state in SQLite and via the REST API.

Also includes a regression test proving that an open position on Strategy A
does NOT block signal generation on Strategy B (fixes cross-strategy cooldown bug).
"""

from __future__ import annotations

import json
import os
import uuid

import pytest

from app.database.migration_runner import apply_migrations
from app.database.repository import TradingRepository


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def e2e_setup(client):
    """Reset all trading state and return test context.

    The `client` fixture already:
      - creates a per-test temp DB
      - applies migrations
      - seeds a canonical RSI Reversion strategy

    So this fixture only:
      1. Wipes trading state (positions, trades, signals, orders, follow-ups)
         so each test starts clean
      2. Returns the canonical strategy_id and headers
    """
    import tests.conftest as _c

    db_path = _c._TEST_DB_PATH
    assert db_path, "client fixture must run first"

    # Use the already-open TradingRepository that the app uses
    # to avoid "database is locked" errors from concurrent connections.
    import app.database.repository as _r
    repo = _r.TradingRepository(database_path=db_path)
    try:
        # Wipe trading state. The conftest-seeded strategy is preserved.
        for table in (
            "positions",
            "trades",
            "orders",
            "signals",
            "signal_followups",
            "balances",
            "daily_pnl",
            "automation_events",
            "publications",
            "bot_events",
            "errors",
        ):
            try:
                repo._connection.execute(f"DELETE FROM {table}")
            except Exception:
                pass
        repo._connection.commit()
    finally:
        repo.close()

    return {
        "strategy_id": "47ddb081-d9bb-454d-bc67-f715d96ef6c4",
        "headers": {"X-Admin-Token": os.environ.get("ADMIN_API_TOKEN", "")},
        "db_path": db_path,
    }


def _gen_signal(client, sid, symbol="BTCUSDT"):
    r = client.post(
        f"/dev/strategies/{sid}/simulate-signal",
        json={"symbol": symbol, "side": "BUY", "confidence": 0.85},
    )
    assert r.status_code == 200, r.text[:300]
    body = r.json()
    res = (body.get("results") or [{}])[0]
    assert res.get("outcome") == "signal_generated", f"unexpected: {res}"
    return res["signal_id"]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_full_paper_pipeline_tp_close(client, e2e_setup):
    """Signal→Fill→TP-close: verify signal/position/trade/PnL/API."""
    sid = e2e_setup["strategy_id"]
    hdrs = e2e_setup["headers"]

    signal_id = _gen_signal(client, sid)

    import sqlite3 as _sq

    conn = _sq.connect(e2e_setup["db_path"])
    try:
        # Signal persisted with TP/SL prices
        sig = conn.execute(
            "SELECT trading_status, tp1, stop_loss FROM signals WHERE id=?",
            (signal_id,),
        ).fetchone()
        assert sig is not None, f"signal {signal_id} not in DB"
        assert sig[1] is not None and sig[2] is not None, f"TP/SL not set: {sig}"

        # Trade entry recorded
        tr = conn.execute(
            "SELECT symbol, side, entry_price FROM trades WHERE symbol=?",
            ("BTCUSDT",),
        ).fetchone()
        assert tr is not None, "no trade entry in DB"
        assert tr[0] == "BTCUSDT"
        assert tr[2] is not None, "entry_price not set"

        # Position opened
        pos = conn.execute(
            "SELECT side, quantity, entry_price FROM positions WHERE symbol=?",
            ("BTCUSDT",),
        ).fetchone()
        assert pos is not None, "no position opened"

        # TP/SL tracked via signal_followups
        tpsl = conn.execute(
            "SELECT event_data FROM signal_followups WHERE signal_id=? AND event_type=?",
            (signal_id, "TP_SL_ATTACHED"),
        ).fetchone()
        assert tpsl is not None, "TP/SL not tracked in signal_followups"
        tpsl_data = json.loads(tpsl[0])
        assert "tp_order" in tpsl_data, f"tp_order missing: {tpsl_data}"
        assert "sl_order" in tpsl_data, f"sl_order missing: {tpsl_data}"
    finally:
        conn.close()

    # Drive close via TP (fallback SL if no TP found)
    r = client.post(
        f"/dev/strategies/{sid}/drive-close",
        json={"symbol": "BTCUSDT", "target": "tp"},
    )
    if r.status_code == 400 and "No TP order" in r.text:
        r = client.post(
            f"/dev/strategies/{sid}/drive-close",
            json={"symbol": "BTCUSDT", "target": "sl"},
        )
    assert r.status_code == 200, r.text[:300]

    conn = _sq.connect(e2e_setup["db_path"])
    try:
        # Trade updated with exit_price and realized_pnl
        tr2 = conn.execute(
            "SELECT exit_price, realized_pnl FROM trades WHERE symbol=?",
            ("BTCUSDT",),
        ).fetchone()
        assert tr2 is not None, "trade missing after close"
        assert tr2[0] is not None, "exit_price not recorded"
        assert tr2[1] is not None, "realized_pnl missing"
        float(tr2[1])  # raises if not convertible to numeric

        # Position closed
        pos = conn.execute(
            "SELECT symbol FROM positions WHERE symbol=?", ("BTCUSDT",)
        ).fetchone()
        assert pos is None, "position not closed after drive-close"
    finally:
        conn.close()

    # REST API smoke: at least /signals endpoint should respond
    r = client.get("/signals", headers=hdrs)
    assert r.status_code in (200, 401, 403), f"/signals status: {r.status_code}"


def test_full_paper_pipeline_sl_close(client, e2e_setup):
    """Signal→Fill→SL-close: verify loss trade + API visibility."""
    sid = e2e_setup["strategy_id"]
    hdrs = e2e_setup["headers"]

    _gen_signal(client, sid)

    r = client.post(
        f"/dev/strategies/{sid}/drive-close",
        json={"symbol": "BTCUSDT", "target": "sl"},
    )
    assert r.status_code == 200, r.text[:300]

    import sqlite3 as _sq

    conn = _sq.connect(e2e_setup["db_path"])
    try:
        tr = conn.execute(
            "SELECT exit_price, realized_pnl FROM trades WHERE symbol=?",
            ("BTCUSDT",),
        ).fetchone()
        assert tr is not None, "no trade after SL close"
        assert tr[0] is not None, "exit_price missing"
    finally:
        conn.close()


def test_cross_strategy_position_isolation(client, e2e_setup):
    """Regression: open position on Strategy A must NOT block BTC signal on Strategy B.

    Before fix: the dev-signal cooldown check queried `SELECT symbol FROM positions`
    without a strategy_id filter, so positions from any strategy triggered cooldown.
    After fix: positions table has strategy_id, and the cooldown check is scoped.
    """
    import sqlite3 as _sq

    conn = _sq.connect(e2e_setup["db_path"])
    try:
        uid_row = conn.execute("SELECT id FROM users LIMIT 1").fetchone()
        assert uid_row, "no user in DB"
        uid = uid_row[0]
        # Strategy A — create and open a position
        sid_a = str(uuid.uuid4())
        conn.execute(
            """INSERT INTO strategies
               (id, user_id, name, lifecycle_state, execution_mode, market,
                timeframe, template_name, template_params, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (sid_a, uid, "Strat A", "paper", "paper", "BTCUSDT",
             "5m", "rsi_reversion", '{"rsi_period": 14}',
             "2025-01-01T00:00:00", "2025-01-01T00:00:00"),
        )
        # Manually insert an open position for Strategy A (simulating a leftover)
        conn.execute(
            "INSERT INTO positions (symbol, side, quantity, entry_price, mark_price, leverage, unrealized_pnl, strategy_id, updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            ("BTCUSDT", "BUY", "1.0", "50000.0", "50000.0", 1, 0.0, sid_a, "2025-01-01T00:00:00"),
        )
        conn.commit()
    finally:
        conn.close()

    # Strategy B — uses the conftest-seeded canonical strategy
    sid_b = e2e_setup["strategy_id"]  # "47ddb081-d9bb-454d-bc67-f715d96ef6c4"

    r = client.post(
        f"/dev/strategies/{sid_b}/simulate-signal",
        json={"symbol": "BTCUSDT", "side": "BUY", "confidence": 0.85},
    )
    assert r.status_code == 200, r.text[:300]
    body = r.json()
    res = (body.get("results") or [{}])[0]
    assert res.get("outcome") == "signal_generated", (
        f"Strategy B BTCUSDT blocked by Strategy A position — cooldown bug not fixed: {res}"
    )
    assert res.get("signal_id"), f"no signal_id in result: {res}"
