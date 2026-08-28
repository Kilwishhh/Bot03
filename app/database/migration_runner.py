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
