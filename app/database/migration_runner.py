"""Idempotent migration runner. Runs SQL files from app/database/migrations
in name order, recording each applied migration in schema_migrations.

All scripts must be idempotent: re-running on an already-applied migration
is a no-op (uses IF NOT EXISTS / IF EXISTS guards and backfill updates that
only touch NULL rows).
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

from app.database.migrations._manifest import MIGRATIONS

logger = logging.getLogger(__name__)

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


def applied_migrations(conn: sqlite3.Connection) -> set[str]:
    """Return the set of migration names already applied."""
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations ("
        "  name TEXT PRIMARY KEY,"
        "  applied_at TEXT NOT NULL"
        ")"
    )
    rows = conn.execute("SELECT name FROM schema_migrations").fetchall()
    return {row[0] for row in rows}


def apply_migrations(conn: sqlite3.Connection, dry_run: bool = False) -> list[str]:
    """Apply any unapplied migrations in order. Returns the list applied.

    Each migration is committed individually. If a migration raises, the
    runner stops and re-raises so the caller sees the failure.
    """
    already = applied_migrations(conn)
    applied: list[str] = []

    for name in MIGRATIONS:
        if name in already:
            continue

        path = MIGRATIONS_DIR / f"{name}.sql"
        if not path.exists():
            raise FileNotFoundError(f"Migration file missing: {path}")

        sql = path.read_text(encoding="utf-8")
        logger.info("Applying migration: %s (dry_run=%s)", name, dry_run)

        if name == "013_relax_timeframe_check" and not _has_column(conn, "strategies", "universe_type"):
            # Pre-012 DBs don't have universe_type; skip this migration
            # (the old narrow CHECK won't reject any existing timeframe values)
            logger.info("Skipping 013: strategies.universe_type not present (pre-012 DB)")
            with conn:
                conn.execute(
                    "INSERT INTO schema_migrations (name, applied_at) VALUES (?, ?)",
                    (name, _now_iso()),
                )
            applied.append(name)
            continue

        if name == "014_extend_signals_full" and not dry_run:
            # Idempotent: only add columns that don't already exist.
            with conn:
                _exec_one(conn, "ALTER TABLE signals ADD COLUMN signal_id TEXT")
                _exec_one(conn, "ALTER TABLE signals ADD COLUMN strategy_id TEXT")
                _exec_one(conn, "ALTER TABLE signals ADD COLUMN strategy_name TEXT")
                _exec_one(conn, "ALTER TABLE signals ADD COLUMN entry TEXT")
                _exec_one(conn, "ALTER TABLE signals ADD COLUMN take_profit TEXT")
                _exec_one(conn, "ALTER TABLE signals ADD COLUMN stop_loss TEXT")
                _exec_one(conn, "ALTER TABLE signals ADD COLUMN timeframe TEXT")
                _exec_one(conn, "ALTER TABLE signals ADD COLUMN mode TEXT NOT NULL DEFAULT 'paper'")
                _exec_one(conn, "ALTER TABLE signals ADD COLUMN signal_status TEXT NOT NULL DEFAULT 'active'")
                _exec_one(conn, "ALTER TABLE signals ADD COLUMN trading_status TEXT NOT NULL DEFAULT 'pending'")
                _exec_one(conn, "ALTER TABLE signals ADD COLUMN telegram_status TEXT NOT NULL DEFAULT 'pending'")
                _exec_one(conn, "ALTER TABLE signals ADD COLUMN square_status TEXT NOT NULL DEFAULT 'pending'")
                _exec_one(conn, "ALTER TABLE signals ADD COLUMN created_at TEXT")
                _exec_one(conn, "ALTER TABLE signals ADD COLUMN updated_at TEXT")
                _exec_one(conn, "ALTER TABLE signals ADD COLUMN candle_close_time TEXT")
                _exec_one(conn, "ALTER TABLE signals ADD COLUMN indicators TEXT")
                _exec_one(conn, "ALTER TABLE signals ADD COLUMN reasons TEXT")
                conn.execute(
                    "CREATE UNIQUE INDEX IF NOT EXISTS uq_signals_signal_id "
                    "ON signals(signal_id) WHERE signal_id IS NOT NULL"
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_signals_strategy_id "
                    "ON signals(strategy_id, created_at DESC)"
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_signals_symbol_tf "
                    "ON signals(symbol, timeframe, created_at DESC)"
                )
                conn.execute(
                    "INSERT INTO schema_migrations (name, applied_at) VALUES (?, ?)",
                    (name, _now_iso()),
                )
            applied.append(name)
            continue

        if name == "015_condition_confidence" and not dry_run:
            # Idempotent: add confidence_hits and confidence_total columns.
            with conn:
                _exec_one(conn, "ALTER TABLE signals ADD COLUMN confidence_hits INTEGER")
                _exec_one(conn, "ALTER TABLE signals ADD COLUMN confidence_total INTEGER")
                conn.execute(
                    "INSERT INTO schema_migrations (name, applied_at) VALUES (?, ?)",
                    (name, _now_iso()),
                )
            applied.append(name)
            continue

        if not dry_run:
            with conn:  # transaction context — commits on success
                conn.executescript(sql)
                conn.execute(
                    "INSERT INTO schema_migrations (name, applied_at) VALUES (?, ?)",
                    (name, _now_iso()),
                )
        applied.append(name)

    return applied


def _now_iso() -> str:
    from datetime import UTC, datetime
    return datetime.now(UTC).isoformat()


def _has_column(conn: sqlite3.Connection, table: str, column: str) -> bool:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(row[1] == column for row in rows)


def _exec_one(conn: sqlite3.Connection, sql: str) -> bool:
    """Execute a single SQL statement, returning False on duplicate-column.

    Used by migrations 014+ to make ADD COLUMN idempotent (SQLite has no
    `ADD COLUMN IF NOT EXISTS`). Returns True on success, False on the
    expected "duplicate column name" error, raises on any other error.
    """
    try:
        conn.execute(sql)
        return True
    except sqlite3.OperationalError as exc:
        if "duplicate column name" in str(exc).lower():
            return False
        raise
