"""Shared test fixtures — runs before any test module imports app modules."""

import os

# Capture the canonical test token at module load — before any test has a chance
# to override ADMIN_API_TOKEN.  This is the value we restore after every test.
_ORIGINAL_ADMIN_TOKEN = os.environ.get(
    "ADMIN_API_TOKEN", "test-admin-secret-token-12345"
)
os.environ.setdefault("CONTROL_API_TOKEN", "test-control-secret-token-67890")
os.environ.setdefault("TRADING_MODE", "paper")
os.environ.setdefault("DATABASE_PATH", ":memory:")
os.environ.setdefault("API_RATE_LIMIT_PER_MINUTE", "1000")  # effectively disable in tests
# Explicitly disable remote control in tests so test_remote_control_is_disabled_by_default
# is not affected by a project-level .env file that enables it.
os.environ["ENABLE_REMOTE_CONTROL"] = "false"


import pathlib

# Tests need a real file-based DB so connections see the same state.
# :memory: would give each sqlite3.connect() a fresh database and resets
# would silently fail. Use a per-session temp file instead.
import tempfile

import pytest
from fastapi.testclient import TestClient

_DB_DIR = pathlib.Path(tempfile.mkdtemp(prefix="mktrader-test-"))
os.environ["DATABASE_PATH"] = str(_DB_DIR / "trading.db")

# Import after env vars are set so the app picks up the right DATABASE_PATH
# Ensure dev routes are always registered at import time, not just inside the
# client fixture — some test files (test_strategy_test_001.py) use a module-level
# TestClient and never call the fixture. Without this, those tests get 404s.
from app.api.routes import dev_routes as _dr
from app.api.server import app

if not any("/dev/" in (r.path if hasattr(r, "path") else "")
           for _router in app.routes
           for r in (_router.routes if hasattr(_router, "routes") else [_router])):
    app.include_router(_dr.router)

# Session DB is created with proper migrations at import time.
# Per-test fixtures each get their own isolated temp DB via tmp_path.
# We do NOT seed the session DB with hardcoded rows — that caused stale-schema
# INSERT failures when migration 012 added new columns after the session DB
# had already been seeded with the old schema.
import sqlite3 as _sql_seed
import uuid as _uuid_seed
from datetime import datetime as _dt_seed

_SESSION_DB = os.environ["DATABASE_PATH"]

# Exposed so test fixtures (e.g. test_p001_paper_e2e) can use the same
# per-test DB that the client fixture's patched TradingRepository uses.
_TEST_DB_PATH: str | None = None
_session_conn = _sql_seed.connect(_SESSION_DB)
try:
    # Force schema creation + apply all migrations on this DB
    from app.database.repository import TradingRepository as _SeedRepo
    _SeedRepo(database_path=_SESSION_DB)
    from app.database.migration_runner import apply_migrations as _apply_mig
    _apply_mig(_session_conn)
    # Seed canonical test strategy and user in the session DB
    _strat_id = "47ddb081-d9bb-454d-bc67-f715d96ef6c4"
    _user_id = str(_uuid_seed.uuid4())
    _now = _dt_seed.now().isoformat()
    _session_conn.execute(
        "INSERT OR IGNORE INTO users (id, email, password_hash, display_name, role, status, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, 'user', 'active', ?, ?)",
        (_user_id, "test@local.dev", "x", "Test User", _now, _now),
    )
    _session_conn.execute(
        "INSERT OR REPLACE INTO strategies "
        "(id, user_id, name, description, version, lifecycle_state, execution_mode, execution_venue, "
        "market, timeframe, entry_config, exit_config, risk_config, template_name, template_params, "
        "created_at, updated_at, "
        "universe_type, universe_config, confirmation_timeframes, "
        "indicators_config, conditions_config, filters_config, confidence_config, notes) "
        "VALUES (?, ?, 'RSI Reversion 1M Test', 'E2E test fixture', 1, 'paper', 'paper', 'binance', "
        " 'BTCUSDT,ETHUSDT,SOLUSDT', '1m', '{}', "
        " '{\"tp1_pct\":0.003,\"stop_loss_pct\":0.005}', '{}', "
        " 'rsi_reversion_1m_test', '{\"symbols\":[\"BTCUSDT\",\"ETHUSDT\",\"SOLUSDT\"]}', ?, ?, "
        " 'custom_watchlist', '{\"symbols\":[\"BTCUSDT\",\"ETHUSDT\",\"SOLUSDT\"]}', '[]', "
        " '[]', '{}', '{}', '{}', NULL)",
        (_strat_id, _user_id, _now, _now),
    )
    _session_conn.commit()
finally:
    _session_conn.close()


@pytest.fixture
def client(tmp_path):
    """FastAPI TestClient with isolated per-test temp DB and cleared paper adapters.

    Also seeds the canonical RSI Reversion test strategy so the /dev/* endpoints
    can find it.
    """
    import sqlite3 as _sql
    import uuid as _uuid
    from datetime import datetime as _dt
    test_db = str(tmp_path / "trading.db")
    import tests.conftest as _c
    _c._TEST_DB_PATH = test_db

    # Patch TradingRepository so TradingRepository() (no args) uses the per-test temp DB
    import app.database.repository as _r
    _original_init = _r.TradingRepository.__init__

    def _patched_init(self, database_path=None):
        if database_path is None:
            database_path = test_db
        _original_init(self, database_path)

    _r.TradingRepository.__init__ = _patched_init

    # Clear the cached default repository so admin_routes re-creates it
    # against the per-test temp DB (not the session DB from conftest import time).
    import app.database.repository as _r2
    _r2._default_repo = None

    # Ensure dev routes are registered (they may have been silently dropped at import
    # if a prior import step failed — add them here so TestClient sees them)
    from app.api.routes import dev_routes as _dr
    from app.api.server import app as _app
    _app.include_router(_dr.router)  # router already has prefix="/dev"

    # Clear per-test paper-adapter state
    _dr._paper_adapters.clear()

    # Seed a user + the RSI Reversion test strategy in the temp DB so the dev
    # endpoints have something to look up. We use sqlite3 directly to avoid
    # pulling in the full auth/strategy service stack for a test fixture.
    _strat_id = "47ddb081-d9bb-454d-bc67-f715d96ef6c4"
    _now = _dt.now().isoformat()

    # Force schema creation + apply all migrations on this DB file
    _repo_for_schema = _r.TradingRepository(database_path=test_db)
    del _repo_for_schema
    # Apply migrations so signal_followups and other extended tables exist
    import sqlite3 as _sql2
    _mconn = _sql2.connect(test_db)
    try:
        from app.database.migration_runner import apply_migrations
        apply_migrations(_mconn)
    finally:
        _mconn.close()

    _conn = _sql.connect(test_db)
    try:
        _user_id = str(_uuid.uuid4())
        _conn.execute(
            "INSERT OR IGNORE INTO users (id, email, password_hash, display_name, role, status, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, 'user', 'active', ?, ?)",
            (_user_id, "test@local.dev", "x", "Test User", _now, _now),
        )
        _conn.execute(
            "INSERT OR REPLACE INTO strategies "
            "(id, user_id, name, description, version, lifecycle_state, execution_mode, execution_venue, "
            "market, timeframe, entry_config, exit_config, risk_config, template_name, template_params, "
            "created_at, updated_at, "
            "universe_type, universe_config, confirmation_timeframes, "
            "indicators_config, conditions_config, filters_config, confidence_config, notes) "
            "VALUES (?, ?, 'RSI Reversion 1M Test', 'E2E test fixture', 1, 'paper', 'paper', 'binance', "
            " 'BTCUSDT,ETHUSDT,SOLUSDT', '1m', '{}', "
            " '{\"tp1_pct\":0.003,\"stop_loss_pct\":0.005}', '{}', "
            " 'rsi_reversion_1m_test', '{\"symbols\":[\"BTCUSDT\",\"ETHUSDT\",\"SOLUSDT\"]}', ?, ?, "
            " 'custom_watchlist', '{\"symbols\":[\"BTCUSDT\",\"ETHUSDT\",\"SOLUSDT\"]}', '[]', "
            " '[]', '{}', '{}', '{}', NULL)",
            (_strat_id, _user_id, _now, _now),
        )
        _conn.commit()
    finally:
        _conn.close()

    try:
        with TestClient(_app) as tc:
            yield tc
    finally:
        _r.TradingRepository.__init__ = _original_init


@pytest.fixture(autouse=True)
def _reset_remote_control_flag():
    """Restore ENABLE_REMOTE_CONTROL=false AND ADMIN_API_TOKEN before every test.

    Some test modules (e.g. test_e2e_ermis.py) flip ENABLE_REMOTE_CONTROL to "true"
    to exercise the /control/* routes; test_admin_state_machine.py sets
    ADMIN_API_TOKEN to a custom value for its auth bypass fixture. Without this
    autouse fixture the overrides leak into later tests and break token
    verification.
    """
    _original_admin_token = _ORIGINAL_ADMIN_TOKEN
    os.environ["ENABLE_REMOTE_CONTROL"] = "false"
    os.environ["ADMIN_API_TOKEN"] = _original_admin_token
    yield
    os.environ["ENABLE_REMOTE_CONTROL"] = "false"
    os.environ["ADMIN_API_TOKEN"] = _original_admin_token
