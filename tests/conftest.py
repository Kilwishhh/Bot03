"""Shared test fixtures — runs before any test module imports app modules."""

import os

os.environ.setdefault("ADMIN_API_TOKEN", "test-admin-secret-token-12345")
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

# Seed the canonical RSI Reversion test strategy in the session-temp DB so that
# test files which use a module-level TestClient (e.g. test_strategy_test_001.py)
# can resolve the strategy_id without going through the per-test `client` fixture.
# The fixture below also seeds the per-test temp DB for files that use it.
import sqlite3 as _sql_seed
import uuid as _uuid_seed
from datetime import datetime as _dt_seed

_SESSION_DB = os.environ["DATABASE_PATH"]
_session_conn = _sql_seed.connect(_SESSION_DB)
try:
    # Force schema creation by opening a repository on this DB
    from app.database.repository import TradingRepository as _SeedRepo
    _SeedRepo(database_path=_SESSION_DB)
    # Apply migrations so signal_followups and other extended tables exist
    from app.database.migration_runner import apply_migrations as _apply_mig
    _apply_mig(_session_conn)

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
        " market, timeframe, entry_config, exit_config, risk_config, template_name, template_params, "
        " created_at, updated_at) "
        "VALUES (?, ?, 'RSI Reversion 1M Test', 'E2E test fixture', 1, 'paper', 'paper', 'binance', "
        " 'BTCUSDT,ETHUSDT,SOLUSDT', '1m', '{}', "
        " '{\"tp1_pct\":0.003,\"stop_loss_pct\":0.005}', '{}', "
        " 'rsi_reversion_1m_test', '{\"symbols\":[\"BTCUSDT\",\"ETHUSDT\",\"SOLUSDT\"]}', ?, ?)",
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

    # Patch TradingRepository so TradingRepository() (no args) uses the per-test temp DB
    import app.database.repository as _r
    _original_init = _r.TradingRepository.__init__

    def _patched_init(self, database_path=None):
        if database_path is None:
            database_path = test_db
        _original_init(self, database_path)

    _r.TradingRepository.__init__ = _patched_init

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
            " market, timeframe, entry_config, exit_config, risk_config, template_name, template_params, "
            " created_at, updated_at) "
            "VALUES (?, ?, 'RSI Reversion 1M Test', 'E2E test fixture', 1, 'paper', 'paper', 'binance', "
            " 'BTCUSDT,ETHUSDT,SOLUSDT', '1m', '{}', "
            " '{\"tp1_pct\":0.003,\"stop_loss_pct\":0.005}', '{}', "
            " 'rsi_reversion_1m_test', '{\"symbols\":[\"BTCUSDT\",\"ETHUSDT\",\"SOLUSDT\"]}', ?, ?)",
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
    """Restore ENABLE_REMOTE_CONTROL=false before every test.

    Some test modules (e.g. test_e2e_ermis.py) flip this flag to "true" to
    exercise the /control/* routes; without this autouse fixture the override
    leaks into later tests and breaks test_remote_control_is_disabled_by_default.
    """
    os.environ["ENABLE_REMOTE_CONTROL"] = "false"
    yield
    os.environ["ENABLE_REMOTE_CONTROL"] = "false"
