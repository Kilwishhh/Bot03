"""Bot state machine + paper reset + data isolation tests.

Targets the requirements from the phase 5 dashboard work:
- STOPPED / RUNNING / PAUSED states are mutually exclusive
- START actually starts BotRunner; PAUSE/RESUME/STOP actually affect it
- Failed START must not report RUNNING
- Refresh does not mutate trading data
- Paper reset only removes Paper data
- Testnet reset only removes Testnet data
- Live data, strategies, and users survive Paper reset
"""
from __future__ import annotations

import os
import sqlite3
import threading
import time
from decimal import Decimal

import pytest


# ─────────────────────────── BotRunner pause/resume ───────────────────────────


def test_botrunner_initial_state_is_running():
    """Fresh BotRunner is not paused and not stopped."""
    from app.database import TradingRepository
    from app.runtime import BotRunner, TradingCycle

    repo = TradingRepository(":memory:")
    cycle = TradingCycle(
        market_data=_StubMarketData(),
        signals=_StubSignals(),
        orders=_StubOrders(),
        repository=repo,
    )
    runner = BotRunner(cycle, "BTCUSDT", "15m", interval_seconds=0.1)
    assert runner.is_paused is False
    assert runner._stop_requested is False
    repo.close()


def test_botrunner_pause_blocks_cycles():
    """While paused, run_once is NOT called. Only resumes after .resume()."""
    from app.database import TradingRepository
    from app.runtime import BotRunner, TradingCycle

    repo = TradingRepository(":memory:")
    counter = _CounterStrategy()
    cycle = TradingCycle(
        market_data=_StubMarketData(),
        signals=counter,
        orders=_StubOrders(),
        repository=repo,
    )
    runner = BotRunner(cycle, "BTCUSDT", "15m", interval_seconds=0.1)

    runner.pause()
    t = threading.Thread(target=runner.run, kwargs={"max_cycles": 5}, daemon=True)
    t.start()
    time.sleep(0.6)
    # Paused → no cycles
    assert counter.calls <= 1
    # Resume → cycles proceed
    runner.resume()
    t.join(timeout=3)
    assert counter.calls >= 2
    repo.close()


def test_botrunner_stop_unblocks_paused_loop():
    """stop() unblocks a paused loop and exits cleanly."""
    from app.database import TradingRepository
    from app.runtime import BotRunner, TradingCycle

    repo = TradingRepository(":memory:")
    cycle = TradingCycle(
        market_data=_StubMarketData(),
        signals=_CounterStrategy(),
        orders=_StubOrders(),
        repository=repo,
    )
    runner = BotRunner(cycle, "BTCUSDT", "15m", interval_seconds=0.5)
    runner.pause()
    t = threading.Thread(target=runner.run, daemon=True)
    t.start()
    time.sleep(0.2)
    assert t.is_alive()  # stuck on pause
    runner.stop()
    t.join(timeout=2)
    assert not t.is_alive()
    repo.close()


# ────────────────────────────── /admin/control API ────────────────────────────


@pytest.fixture
def admin_client():
    """Spin a TestClient that bypasses remote-control auth for /admin/*."""
    os.environ["ADMIN_API_TOKEN"] = "demo123"
    os.environ["ENABLE_REMOTE_CONTROL"] = "true"
    # Stub StrategyScanner.scan_once so the multi-symbol runner doesn't block on
    # real Binance API calls during the start/stop/pause lifecycle tests.
    import app.strategy.scanner as _scanner_mod
    _orig_scan = _scanner_mod.StrategyScanner.scan_once
    def _stub(self):
        return []
    _scanner_mod.StrategyScanner.scan_once = _stub
    from fastapi.testclient import TestClient
    from app.api.server import app
    yield TestClient(app)
    _scanner_mod.StrategyScanner.scan_once = _orig_scan


def _auth():
    return {"X-Admin-Token": "demo123"}


def test_admin_control_initial_state_is_stopped(admin_client):
    r = admin_client.get("/admin/control", headers=_auth())
    assert r.status_code == 200
    body = r.json()
    assert body["state"] == "stopped"
    assert body["bot_running"] is False
    assert body["paused"] is False


def test_admin_control_start_pause_resume_stop(admin_client):
    """Full lifecycle on the real control endpoint."""
    # STOP → START
    r = admin_client.post("/admin/control/start", headers=_auth())
    assert r.status_code == 200
    # State should become 'running' within a couple of seconds
    deadline = time.time() + 6
    while time.time() < deadline:
        s = admin_client.get("/admin/control", headers=_auth()).json()
        if s["state"] == "running":
            break
        time.sleep(0.3)
    assert s["state"] == "running", f"never reached running, got {s}"
    assert s["bot_running"] is True

    # RUNNING → PAUSED
    r = admin_client.post("/admin/control/pause", headers=_auth())
    assert r.status_code == 200
    time.sleep(1.5)
    s = admin_client.get("/admin/control", headers=_auth()).json()
    assert s["state"] == "paused", f"expected paused, got {s}"
    assert s["paused"] is True
    assert s["bot_running"] is True  # thread still alive, just paused

    # PAUSED → RUNNING
    r = admin_client.post("/admin/control/resume", headers=_auth())
    assert r.status_code == 200
    time.sleep(1.5)
    s = admin_client.get("/admin/control", headers=_auth()).json()
    assert s["state"] == "running", f"expected running, got {s}"
    assert s["paused"] is False

    # RUNNING → STOPPED
    r = admin_client.post("/admin/control/stop", headers=_auth())
    assert r.status_code == 200
    # Wait for thread to actually exit
    deadline = time.time() + 12
    while time.time() < deadline:
        s = admin_client.get("/admin/control", headers=_auth()).json()
        if s["bot_running"] is False:
            break
        time.sleep(0.3)
    assert s["bot_running"] is False, f"thread still alive: {s}"
    assert s["state"] == "stopped"


def test_failed_start_does_not_report_running(monkeypatch):
    """If exchange creation fails, state must remain stopped."""
    os.environ["ADMIN_API_TOKEN"] = "demo123"
    os.environ["ENABLE_REMOTE_CONTROL"] = "true"

    from app.api import control as control_mod

    def boom(_settings):
        raise RuntimeError("simulated exchange failure")

    monkeypatch.setattr("app.exchange.create_exchange", boom)
    from fastapi.testclient import TestClient
    from app.api.server import app
    client = TestClient(app)

    r = client.post("/admin/control/start", headers=_auth())
    assert r.status_code == 400
    s = client.get("/admin/control", headers=_auth()).json()
    assert s["state"] == "stopped", f"failed start leaked running: {s}"
    assert s["bot_running"] is False


def test_refresh_does_not_mutate_data(admin_client):
    """GET /dev/stats and /admin/control must be read-only."""
    r1 = admin_client.get("/dev/stats", headers=_auth()).json()
    trades_before = r1.get("closed_trades", 0)
    signals_before = r1.get("total_signals", 0)
    # Hit refresh many times
    for _ in range(5):
        admin_client.get("/admin/control", headers=_auth())
        admin_client.get("/dev/stats", headers=_auth())
    r2 = admin_client.get("/dev/stats", headers=_auth()).json()
    assert r2.get("closed_trades", 0) == trades_before
    assert r2.get("total_signals", 0) == signals_before


# ────────────────────────────── Paper reset API ───────────────────────────────


@pytest.fixture
def populated_db(tmp_path):
    """Build a temp SQLite with paper + testnet + live rows + strategies + users."""
    db = tmp_path / "reset.sqlite3"
    conn = sqlite3.connect(db)
    cur = conn.cursor()
    # Schema (subset, only what /admin/reset touches)
    cur.executescript("""
        CREATE TABLE signals (
            id TEXT PRIMARY KEY, symbol TEXT, side TEXT, confidence REAL,
            timestamp TEXT, strategy TEXT, reason TEXT, user_id TEXT,
            strategy_id TEXT, entry_price REAL, tp1 REAL, tp2 REAL,
            stop_loss REAL, mode TEXT DEFAULT 'paper',
            signal_status TEXT, trading_status TEXT,
            telegram_status TEXT, square_status TEXT,
            created_at TEXT, updated_at TEXT);
        CREATE TABLE trades (
            trade_id TEXT PRIMARY KEY, symbol TEXT, side TEXT,
            quantity REAL, entry_price REAL, exit_price REAL,
            realized_pnl REAL, fees REAL, strategy TEXT,
            entry_time TEXT, exit_time TEXT);
        CREATE TABLE positions (
            symbol TEXT PRIMARY KEY, side TEXT, quantity REAL,
            entry_price REAL, mark_price REAL, leverage INTEGER,
            unrealized_pnl REAL, updated_at TEXT);
        CREATE TABLE orders (id TEXT PRIMARY KEY, payload TEXT);
        CREATE TABLE balances (id TEXT PRIMARY KEY, value REAL);
        CREATE TABLE bot_events (id INTEGER PRIMARY KEY, name TEXT);
        CREATE TABLE errors (id INTEGER PRIMARY KEY, msg TEXT);
        CREATE TABLE daily_pnl (date TEXT PRIMARY KEY, value REAL);
        CREATE TABLE control_state (id INTEGER PRIMARY KEY, state TEXT,
                                    high_water_mark REAL, heartbeat_at TEXT);
        INSERT INTO control_state (id, state) VALUES (1, 'stopped');

        CREATE TABLE strategies (id TEXT PRIMARY KEY, name TEXT,
                                 user_id TEXT, market TEXT,
                                 lifecycle_state TEXT, execution_mode TEXT);
        INSERT INTO strategies VALUES
            ('strat-1', 'TestStrategy', 'user-1', 'BTCUSDT', 'paper', 'paper'),
            ('strat-2', 'LiveStrategy', 'user-1', 'BTCUSDT', 'live', 'live');

        CREATE TABLE users (id TEXT PRIMARY KEY, email TEXT, password_hash TEXT,
                            display_name TEXT, role TEXT, status TEXT,
                            created_at TEXT, updated_at TEXT);
        INSERT INTO users VALUES
            ('user-1', 'a@b.c', 'h', 'A', 'user', 'active', 't', 't');
    """)
    # Paper signals
    for i in range(3):
        cur.execute(
            "INSERT INTO signals (id, symbol, side, mode) VALUES (?,?,?,?)",
            (f"paper-sig-{i}", "BTCUSDT", "BUY", "paper"),
        )
    # Testnet signals
    for i in range(2):
        cur.execute(
            "INSERT INTO signals (id, symbol, side, mode) VALUES (?,?,?,?)",
            (f"testnet-sig-{i}", "BTCUSDT", "BUY", "testnet"),
        )
    # Paper trades
    for i in range(2):
        cur.execute(
            "INSERT INTO trades (trade_id, symbol, side) VALUES (?,?,?)",
            (f"trade-{i}", "BTCUSDT", "BUY"),
        )
    # Paper positions
    cur.execute(
        "INSERT INTO positions VALUES (?,?,?,?,?,?,?,?)",
        ("BTCUSDT", "BUY", 0.01, 50000, 50000, 10, 0, "t"),
    )
    # bot_events/errors (treated as paper for reset)
    for i in range(4):
        cur.execute("INSERT INTO bot_events (name) VALUES (?)", (f"e-{i}",))
        cur.execute("INSERT INTO errors (msg) VALUES (?)", (f"err-{i}",))
    conn.commit()
    conn.close()
    return db


def _counts(db_path):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    out = {
        "signals_paper": cur.execute("SELECT count(*) FROM signals WHERE mode='paper'").fetchone()[0],
        "signals_testnet": cur.execute("SELECT count(*) FROM signals WHERE mode='testnet'").fetchone()[0],
        "trades": cur.execute("SELECT count(*) FROM trades").fetchone()[0],
        "positions": cur.execute("SELECT count(*) FROM positions").fetchone()[0],
        "bot_events": cur.execute("SELECT count(*) FROM bot_events").fetchone()[0],
        "errors": cur.execute("SELECT count(*) FROM errors").fetchone()[0],
        "strategies": cur.execute("SELECT count(*) FROM strategies").fetchone()[0],
        "users": cur.execute("SELECT count(*) FROM users").fetchone()[0],
    }
    conn.close()
    return out


def test_paper_reset_requires_confirmation(monkeypatch, populated_db):
    """Without confirm=true, the HTTP endpoint returns 400 and data is unchanged."""
    os.environ["ADMIN_API_TOKEN"] = "demo123"
    from fastapi.testclient import TestClient
    from app.api.server import app
    client = TestClient(app)
    r = client.post("/admin/reset/paper", headers=_auth())
    assert r.status_code == 400
    # Data unchanged
    c = _counts(populated_db)
    assert c["signals_paper"] == 3
    assert c["trades"] == 2


def test_paper_reset_only_removes_paper(populated_db):
    """Direct call to reset_mode_data removes only paper-mode rows."""
    from app.api.routes.admin_routes import reset_mode_data
    from app.database import TradingRepository
    repo = TradingRepository()
    repo.close()  # discard default
    # Manually bind a fresh repo to the temp db
    import sqlite3 as _sq
    repo = TradingRepository.__new__(TradingRepository)
    repo._connection = _sq.connect(populated_db)
    repo._lock = type("L", (), {"__enter__": lambda s: s, "__exit__": lambda *a: False})()
    counts = reset_mode_data(repo, "paper")
    assert counts["signals_deleted"] == 3
    assert counts["trades_deleted"] == 2
    assert counts["positions_deleted"] == 1
    assert counts["bot_events_deleted"] == 4
    assert counts["errors_deleted"] == 4

    c = _counts(populated_db)
    # Paper signals gone
    assert c["signals_paper"] == 0
    # Testnet signals untouched
    assert c["signals_testnet"] == 2, f"testnet signals were wiped: {c}"
    # Paper trades/positions/events gone
    assert c["trades"] == 0
    assert c["positions"] == 0
    assert c["bot_events"] == 0
    assert c["errors"] == 0
    # Strategies and users UNTOUCHED
    assert c["strategies"] == 2
    assert c["users"] == 1


def test_testnet_reset_keeps_paper_intact(populated_db):
    from app.api.routes.admin_routes import reset_mode_data
    from app.database import TradingRepository
    import sqlite3 as _sq
    repo = TradingRepository.__new__(TradingRepository)
    repo._connection = _sq.connect(populated_db)
    repo._lock = type("L", (), {"__enter__": lambda s: s, "__exit__": lambda *a: False})()
    counts = reset_mode_data(repo, "testnet")
    assert counts["signals_deleted"] == 2
    c = _counts(populated_db)
    # Testnet signals gone
    assert c["signals_testnet"] == 0
    # Paper signals untouched
    assert c["signals_paper"] == 3, f"paper signals wiped by testnet reset: {c}"
    # Strategies and users UNTOUCHED
    assert c["strategies"] == 2
    assert c["users"] == 1


def test_reset_rejects_unknown_mode():
    from app.api.routes.admin_routes import reset_mode_data
    from app.database import TradingRepository
    import sqlite3 as _sq, tempfile
    tmp = tempfile.NamedTemporaryFile(suffix=".sqlite3", delete=False)
    tmp.close()
    repo = TradingRepository.__new__(TradingRepository)
    repo._connection = _sq.connect(tmp.name)
    repo._lock = type("L", (), {"__enter__": lambda s: s, "__exit__": lambda *a: False})()
    with pytest.raises(ValueError):
        reset_mode_data(repo, "invalid")


def test_all_reset_removes_runtime_data_but_preserves_accounts(populated_db):
    from app.api.routes.admin_routes import reset_mode_data
    from app.database import TradingRepository
    repo = TradingRepository.__new__(TradingRepository)
    repo._connection = sqlite3.connect(populated_db)
    repo._lock = type("L", (), {"__enter__": lambda s: s, "__exit__": lambda *a: False})()

    counts = reset_mode_data(repo, "all")

    assert counts["signals_deleted"] == 5
    assert counts["trades_deleted"] == 2
    assert _counts(populated_db)["users"] == 1
    assert _counts(populated_db)["strategies"] == 2


# ────────────────────────────── helpers ──────────────────────────────────────


def _set_repo_db(repo, db_path):
    # Bypass the default __init__ so we can point the repo at the temp db.
    import sqlite3
    repo.__dict__["_connection_override"] = sqlite3.connect(db_path)
    repo.__dict__["_db_path"] = str(db_path)
    # Direct call: install _connection
    repo._connection = sqlite3.connect(db_path)
    repo._lock = type("L", (), {"__enter__": lambda s: s, "__exit__": lambda *a: False})()


class _StubMarketData:
    def candles(self, *_a, **_kw):
        return []


class _StubSignals:
    def generate(self, *_a, **_kw):
        from app.exchange.models import OrderSide
        from app.domain.signal import Signal
        return Signal(symbol="BTCUSDT", side=OrderSide.HOLD, confidence=0.0,
                      reason="stub", strategy="stub")


class _StubOrders:
    def process_signal(self, *_a, **_kw):
        return None
    def balance(self):
        return Decimal("1000")
    def position(self, *_a):
        return None


class _CounterStrategy:
    """A SignalEngine-compatible strategy that records call count."""
    def __init__(self):
        self.calls = 0
    def generate(self, *_a, **_kw):
        self.calls += 1
        from app.exchange.models import OrderSide
        from app.domain.signal import Signal
        return Signal(symbol="BTCUSDT", side=OrderSide.HOLD,
                      confidence=0.0, reason="counter", strategy="counter")
