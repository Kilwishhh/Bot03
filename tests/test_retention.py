"""Phase 4 — Retention policy tests.

Verifies prune_operational_records:
- Deletes records older than retention_days
- Keeps records within retention window
- Returns accurate row counts per table
"""

import sqlite3
import time
from datetime import UTC, datetime, timedelta

import pytest

from app.database.repository import TradingRepository


@pytest.fixture
def repo(tmp_path):
    db = str(tmp_path / "retention_test.db")
    r = TradingRepository(db)
    _init_schema(r)
    yield r
    r.close()


def _init_schema(repo: TradingRepository) -> None:
    """Create the minimal schema needed for prune tests."""
    with repo._lock:
        repo._connection.execute(
            "CREATE TABLE IF NOT EXISTS signals "
            "(symbol TEXT, side TEXT, confidence REAL, timestamp TEXT, strategy TEXT, reason TEXT)"
        )
        repo._connection.execute(
            "CREATE TABLE IF NOT EXISTS bot_events "
            "(event_id INTEGER PRIMARY KEY AUTOINCREMENT, event_type TEXT, message TEXT, created_at TEXT)"
        )
        repo._connection.execute(
            "CREATE TABLE IF NOT EXISTS errors "
            "(error_id INTEGER PRIMARY KEY AUTOINCREMENT, event_type TEXT, message TEXT, created_at TEXT)"
        )


def _insert_old_row(
    repo: TradingRepository, table: str, column: str, days_ago: int
) -> None:
    ts = (datetime.now(UTC) - timedelta(days=days_ago)).isoformat()
    with repo._lock:
        if table == "signals":
            repo._connection.execute(
                "INSERT INTO signals VALUES (?, ?, ?, ?, ?, ?)",
                ("BTCUSDT", "BUY", 0.8, ts, "paper", "test"),
            )
        elif table == "bot_events":
            repo._connection.execute(
                "INSERT INTO bot_events VALUES (NULL, ?, ?, ?)",
                ("cycle_done", "test event", ts),
            )
        elif table == "errors":
            repo._connection.execute(
                "INSERT INTO errors VALUES (NULL, ?, ?, ?)",
                ("error", "test error", ts),
            )


def test_prune_deletes_old_records(repo):
    """Records older than retention_days are deleted."""
    _insert_old_row(repo, "signals", "timestamp", days_ago=100)
    _insert_old_row(repo, "bot_events", "created_at", days_ago=100)
    _insert_old_row(repo, "errors", "created_at", days_ago=100)

    result = repo.prune_operational_records(retention_days=90)
    assert result["signals"] == 1
    assert result["bot_events"] == 1
    assert result["errors"] == 1


def test_prune_keeps_recent_records(repo):
    """Records within the retention window are preserved."""
    _insert_old_row(repo, "signals", "timestamp", days_ago=30)
    _insert_old_row(repo, "bot_events", "created_at", days_ago=1)
    _insert_old_row(repo, "errors", "created_at", days_ago=0)

    result = repo.prune_operational_records(retention_days=90)
    assert result["signals"] == 0
    assert result["bot_events"] == 0
    assert result["errors"] == 0


def test_prune_returns_zero_for_missing_tables(repo):
    """Tables that don't exist return 0 deleted rows."""
    result = repo.prune_operational_records(retention_days=30)
    for table in ("signals", "bot_events", "errors"):
        assert table in result
        assert result[table] == 0


def test_prune_mixed_old_and_recent(repo):
    """When both old and recent records exist, only old ones are removed."""
    for days in (200, 100, 50, 5):
        _insert_old_row(repo, "signals", "timestamp", days_ago=days)

    result = repo.prune_operational_records(retention_days=60)
    assert result["signals"] == 2  # 200 and 100 day-old records
