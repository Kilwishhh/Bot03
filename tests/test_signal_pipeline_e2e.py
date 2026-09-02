"""P0 — Signal pipeline E2E tests.

These tests prove every stage of the signal pipeline works end-to-end
without requiring a live Binance connection. They use a stub market-data
provider so the scanner can be exercised in isolation.

Each test asserts ONE pipeline stage so failures pinpoint exactly where
the pipeline broke.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path


# ---------------------------------------------------------------------------
# Stubs
# ---------------------------------------------------------------------------


@dataclass
class _StubCandle:
    open_time: datetime
    close_time: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


class _StubMarketData:
    """Stub MarketDataProvider. Records every call. Returns fresh 1m candles."""

    def __init__(self, symbols: list[str]) -> None:
        self._symbols = list(symbols)
        self._calls: list[tuple[str, str, int]] = []
        self._now = datetime.now(UTC).replace(second=0, microsecond=0)

    def list_symbols(self) -> list[str]:
        return list(self._symbols)

    def candles(self, symbol: str, timeframe: str, limit: int = 200) -> list[_StubCandle]:
        self._calls.append((symbol, timeframe, limit))
        out = []
        end = self._now - timedelta(minutes=1)
        for i in range(limit):
            t = end - timedelta(minutes=limit - 1 - i)
            out.append(_StubCandle(
                t, t + timedelta(minutes=1) - timedelta(milliseconds=1),
                100.0, 101.0, 99.0, 100.5, 1000.0,
            ))
        return out


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------


def _build_temp_db() -> Path:
    import tempfile
    return Path(tempfile.mkdtemp(prefix="mktrader-e2e-")) / "trading.db"


def _seed_db(path: Path):
    """Initialize schema, apply migrations, create system user. Return repo."""
    conn = sqlite3.connect(str(path), check_same_thread=False, isolation_level=None)
    from app.database.repository import TradingRepository
    from app.database.migration_runner import apply_migrations
    TradingRepository(str(path))
    apply_migrations(conn)
    now = datetime.now(UTC).isoformat()
    conn.execute(
        "INSERT INTO users (id,email,password_hash,display_name,role,status,created_at,updated_at) "
        "VALUES (?,?,?,?,?,?,?,?)",
        ("system-test", "system@test.local", "!", "System", "system", "active", now, now),
    )
    return TradingRepository(str(path))


def _insert_strategy(
    repo,
    *,
    name: str = "TEST_PIPELINE_STRATEGY",
    timeframe: str = "1m",
    universe_type: str = "custom_watchlist",
    universe_config: dict | None = None,
    conditions_config: dict | None = None,
    lifecycle_state: str = "paper",
    execution_mode: str = "paper",
):
    """Insert a strategy. universe_config is REQUIRED — callers must pass it explicitly."""
    sid = str(uuid.uuid4())
    now = datetime.now(UTC).isoformat()
    if universe_config is None:
        universe_config = {"symbols": ["BTCUSDT"]}
    if conditions_config is None:
        conditions_config = {
            "logic": "all",
            "groups": [
                {"logic": "all", "conditions": [{"field": "PRICE", "op": ">", "value": 0}]}
            ],
        }
    repo.db.execute(
        "INSERT INTO strategies (id,user_id,name,description,version,lifecycle_state,"
        "execution_mode,execution_venue,market,timeframe,entry_config,exit_config,"
        "risk_config,template_name,template_params,created_at,updated_at,universe_type,"
        "universe_config,indicators_config,conditions_config,filters_config,"
        "confidence_config,notes) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            sid, "system-test", name, "test", 1,
            lifecycle_state, execution_mode, "binance",
            "binance_futures", timeframe,
            json.dumps({}), json.dumps({"take_profit_pct": 1.0, "stop_loss_pct": 0.5}), json.dumps({}),
            None, json.dumps({}), now, now,
            universe_type, json.dumps(universe_config),
            json.dumps([]), json.dumps(conditions_config),
            json.dumps({}), json.dumps({}),
            "test",
        ),
    )
    return sid


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

import pytest  # noqa: E402


def test_1m_strategy_evaluated_at_configured_timeframe():
    """A 1m strategy must be evaluated with a 1m candle fetch (no hidden 15m fallback)."""
    from app.strategy.scanner import StrategyScanner

    db_path = _build_temp_db()
    repo = _seed_db(db_path)
    _insert_strategy(
        repo, timeframe="1m",
        universe_config={"symbols": ["BTCUSDT", "ETHUSDT", "SOLUSDT"]},
    )

    md = _StubMarketData(["BTCUSDT", "ETHUSDT", "SOLUSDT"])
    scanner = StrategyScanner(repo, md)
    scanner.scan_once()
    last = scanner.diagnostics.snapshot()["last_cycle"]

    assert all(tf == "1m" for _, tf, _ in md._calls), \
        f"non-1m candle fetches: {md._calls}"
    assert last["symbols_evaluated"] == 3


def test_custom_timeframe_reaches_scanner():
    """A 5m strategy must pass its timeframe through to the candle fetch."""
    from app.strategy.scanner import StrategyScanner

    db_path = _build_temp_db()
    repo = _seed_db(db_path)
    _insert_strategy(repo, timeframe="5m", universe_config={"symbols": ["BTCUSDT"]})

    md = _StubMarketData(["BTCUSDT"])
    scanner = StrategyScanner(repo, md)
    scanner.scan_once()

    tfs = {tf for _, tf, _ in md._calls}
    assert tfs == {"5m"}, f"expected 5m only, got {tfs}"


def test_multi_symbol_universe_iterated():
    """A 3-symbol universe must produce 3 evaluations, not collapse to BTCUSDT-only."""
    from app.strategy.scanner import StrategyScanner

    db_path = _build_temp_db()
    repo = _seed_db(db_path)
    _insert_strategy(
        repo, universe_config={"symbols": ["BTCUSDT", "ETHUSDT", "SOLUSDT"]},
    )

    md = _StubMarketData(["BTCUSDT", "ETHUSDT", "SOLUSDT"])
    scanner = StrategyScanner(repo, md)
    scanner.scan_once()
    last = scanner.diagnostics.snapshot()["last_cycle"]

    assert last["symbols_loaded"] == 3
    assert last["symbols_evaluated"] == 3
    assert {s for s, _, _ in md._calls} == {"BTCUSDT", "ETHUSDT", "SOLUSDT"}


def test_fresh_candle_required():
    """Stale candles must not produce a signal."""
    from app.strategy.scanner import StrategyScanner

    db_path = _build_temp_db()
    repo = _seed_db(db_path)
    _insert_strategy(repo, universe_config={"symbols": ["BTCUSDT"]})

    class _StaleMarketData(_StubMarketData):
        def candles(self, symbol, timeframe, limit=200):
            now = datetime.now(UTC).replace(second=0, microsecond=0)
            out = []
            for i in range(limit):
                t = now - timedelta(minutes=limit - i) - timedelta(hours=1)
                out.append(_StubCandle(
                    t, t + timedelta(minutes=1) - timedelta(milliseconds=1),
                    100.0, 101.0, 99.0, 100.5, 1000.0,
                ))
            return out

    md = _StaleMarketData(["BTCUSDT"])
    scanner = StrategyScanner(repo, md)
    signals = scanner.scan_once()
    last = scanner.diagnostics.snapshot()["last_cycle"]
    assert last["fresh_candles"] == 0
    assert last["signals_created"] == 0
    assert signals == []


def test_always_true_creates_signal():
    """ALWAYS_TRUE condition must produce a signal when a fresh candle exists."""
    from app.strategy.scanner import StrategyScanner

    db_path = _build_temp_db()
    repo = _seed_db(db_path)
    _insert_strategy(
        repo, universe_config={"symbols": ["BTCUSDT", "ETHUSDT", "SOLUSDT"]},
    )

    md = _StubMarketData(["BTCUSDT", "ETHUSDT", "SOLUSDT"])
    scanner = StrategyScanner(repo, md)
    signals = scanner.scan_once()
    last = scanner.diagnostics.snapshot()["last_cycle"]

    assert last["signals_created"] == 3, f"want 3, got {last['signals_created']}"
    assert last["conditions_passed"] == 3
    assert {s.symbol for s in signals} == {"BTCUSDT", "ETHUSDT", "SOLUSDT"}


def test_signal_persisted_to_db():
    """Generated signals must be persisted to the signals table."""
    from app.strategy.scanner import StrategyScanner

    db_path = _build_temp_db()
    repo = _seed_db(db_path)
    _insert_strategy(repo, universe_config={"symbols": ["BTCUSDT"]})

    md = _StubMarketData(["BTCUSDT"])
    scanner = StrategyScanner(repo, md)
    signals = scanner.scan_once()

    rows = repo.db.execute(
        "SELECT strategy, symbol, side, entry, timeframe, mode FROM signals"
    ).fetchall()
    assert len(rows) == 1
    assert rows[0][1] == "BTCUSDT"
    # Entry price from stub candle close (100.5)
    assert abs(float(rows[0][3]) - 100.5) < 0.001
    assert rows[0][5] == "paper"
    assert rows[0][4] == "1m"


def test_signal_visible_through_signal_service():
    """The persisted signal must be retrievable through SignalService.list()."""
    from app.strategy.scanner import StrategyScanner
    from app.services.signal_service import SignalService
    from app.core.rbac import AccessContext
    from app.domain.user import User, UserRole, UserStatus

    db_path = _build_temp_db()
    repo = _seed_db(db_path)
    _insert_strategy(repo, universe_config={"symbols": ["BTCUSDT"]})

    md = _StubMarketData(["BTCUSDT"])
    scanner = StrategyScanner(repo, md)
    scanner.scan_once()

    # SignalService.__init__ takes a db path string, not a TradingRepository
    svc = SignalService(str(db_path))
    admin = User(
        id="system-test", email="s@x", display_name="s",
        role=UserRole.ADMIN, status=UserStatus.ACTIVE,
        created_at=datetime.now(UTC), updated_at=datetime.now(UTC),
        password_hash="!",
    )
    items = svc.list(AccessContext(user=admin), limit=10)
    assert len(items) >= 1
    syms = {getattr(s, "symbol", None) for s in items}
    assert "BTCUSDT" in syms


def test_dedup_prevents_duplicate_signals_for_same_candle():
    """Two scan cycles within the same 1m candle must not double-emit."""
    from app.strategy.scanner import StrategyScanner

    db_path = _build_temp_db()
    repo = _seed_db(db_path)
    _insert_strategy(repo, universe_config={"symbols": ["BTCUSDT"]})

    md = _StubMarketData(["BTCUSDT"])
    scanner = StrategyScanner(repo, md)
    scanner.scan_once()
    s1 = scanner.diagnostics.snapshot()["last_cycle"]["signals_created"]

    scanner.scan_once()  # same candle window
    s2 = scanner.diagnostics.snapshot()["last_cycle"]["signals_created"]

    assert s1 == 1
    assert s2 == 0  # deduped
    total = int(repo.db.execute("SELECT COUNT(*) FROM signals").fetchone()[0])
    assert total == 1


def test_one_symbol_failure_does_not_stop_scanner():
    """A failure in one symbol must not block the rest."""
    from app.strategy.scanner import StrategyScanner

    db_path = _build_temp_db()
    repo = _seed_db(db_path)
    _insert_strategy(
        repo, universe_config={"symbols": ["GOOD1", "BAD", "GOOD2"]},
    )

    class _PartialMarketData(_StubMarketData):
        def candles(self, symbol, timeframe, limit=200):
            if symbol == "BAD":
                raise RuntimeError("simulated candle failure")
            return super().candles(symbol, timeframe, limit)

    md = _PartialMarketData(["GOOD1", "BAD", "GOOD2"])
    scanner = StrategyScanner(repo, md)
    signals = scanner.scan_once()
    last = scanner.diagnostics.snapshot()["last_cycle"]

    syms = {s.symbol for s in signals}
    assert "GOOD1" in syms and "GOOD2" in syms
    assert "BAD" not in syms
    assert last["symbols_skipped"] >= 1
    # skip_reasons is keyed by reason code
    assert "fetch_error" in last.get("skip_reasons", {})


def test_strategy_specific_cooldown_does_not_block_other_strategies():
    """Dedup is keyed by (strategy, symbol, candle) — different strategies must not block each other."""
    from app.strategy.scanner import StrategyScanner

    db_path = _build_temp_db()
    repo = _seed_db(db_path)
    _insert_strategy(
        repo, name="STRAT_A",
        universe_config={"symbols": ["BTCUSDT", "ETHUSDT"]},
    )
    _insert_strategy(
        repo, name="STRAT_B",
        universe_config={"symbols": ["BTCUSDT", "ETHUSDT"]},
    )

    md = _StubMarketData(["BTCUSDT", "ETHUSDT"])
    scanner = StrategyScanner(repo, md)
    signals = scanner.scan_once()

    # 2 strategies x 2 symbols = 4 signals
    assert len(signals) == 4, f"want 4, got {len(signals)}"
    names = {s.strategy_name for s in signals}
    assert names == {"STRAT_A", "STRAT_B"}


def test_paper_signal_uses_market_derived_price():
    """Entry price must come from the live candle close, not a hardcoded value."""
    from app.strategy.scanner import StrategyScanner

    db_path = _build_temp_db()
    repo = _seed_db(db_path)
    _insert_strategy(
        repo, universe_config={"symbols": ["BTCUSDT", "ETHUSDT"]},
    )

    class _PricedMarketData(_StubMarketData):
        def candles(self, symbol, timeframe, limit=200):
            now = datetime.now(UTC).replace(second=0, microsecond=0)
            out = []
            price = {"BTCUSDT": 12345.67, "ETHUSDT": 3456.78}.get(symbol, 100.0)
            for i in range(limit):
                t = now - timedelta(minutes=limit - i)
                out.append(_StubCandle(
                    t, t + timedelta(minutes=1) - timedelta(milliseconds=1),
                    price, price + 1, price - 1, price, 1000.0,
                ))
            return out

    md = _PricedMarketData(["BTCUSDT", "ETHUSDT"])
    scanner = StrategyScanner(repo, md)
    signals = scanner.scan_once()
    by_sym = {s.symbol: s.entry for s in signals}
    assert abs(by_sym["BTCUSDT"] - 12345.67) < 0.01
    assert abs(by_sym["ETHUSDT"] - 3456.78) < 0.01


def test_diagnostic_strategy_cannot_be_promoted_to_live():
    """SIGNAL_PIPELINE_TEST must be rejected from LIVE transitions."""
    from app.services.strategy_lifecycle import StrategyLifecycle
    from app.services.strategy_service import StrategyService
    from app.core.rbac import AccessContext
    from app.core.errors import LiveDeploymentError
    from app.domain.strategy import LifecycleState
    from app.domain.user import User, UserRole, UserStatus

    db_path = _build_temp_db()
    repo = _seed_db(db_path)
    from app.seed.signal_pipeline_test import seed
    sid = seed(repo=repo)

    admin = User(
        id="system-test", email="s@x", display_name="s",
        role=UserRole.ADMIN, status=UserStatus.ACTIVE,
        created_at=datetime.now(UTC), updated_at=datetime.now(UTC),
        password_hash="!",
    )
    svc = StrategyService(str(db_path))
    items = svc.list_all(AccessContext(user=admin))
    s = next(x for x in items if x.id == sid)

    lifecycle = StrategyLifecycle(svc)
    with pytest.raises(LiveDeploymentError):
        lifecycle.transition(s, LifecycleState.LIVE, AccessContext(user=admin))


def test_diagnostic_endpoint_returns_pipeline_counters():
    """Diagnostics snapshot must expose every pipeline counter."""
    from app.strategy.scanner import StrategyScanner

    db_path = _build_temp_db()
    repo = _seed_db(db_path)
    _insert_strategy(repo, universe_config={"symbols": ["BTCUSDT"]})
    md = _StubMarketData(["BTCUSDT"])
    scanner = StrategyScanner(repo, md)
    scanner.scan_once()
    snap = scanner.diagnostics.snapshot()
    assert "last_cycle" in snap
    last = snap["last_cycle"]
    for k in (
        "symbols_loaded", "symbols_evaluated", "symbols_with_candles",
        "fresh_candles", "signals_created", "signals_persisted",
        "last_error",
    ):
        assert k in last, f"missing key: {k}"
