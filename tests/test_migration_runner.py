import sqlite3

from app.database.migration_runner import apply_migrations


def test_migrations_reconcile_existing_positions_strategy_id():
    conn = sqlite3.connect(":memory:")
    conn.executescript(
        """
        CREATE TABLE positions (
            id TEXT PRIMARY KEY,
            strategy_id TEXT
        );
        CREATE TABLE strategies (
            id TEXT PRIMARY KEY
        );
        CREATE TABLE signals (
            id TEXT PRIMARY KEY,
            symbol TEXT,
            side TEXT,
            confidence REAL,
            timestamp TEXT
        );
        CREATE TABLE schema_migrations (name TEXT PRIMARY KEY, applied_at TEXT NOT NULL);
        """
    )
    conn.executemany(
        "INSERT INTO schema_migrations (name, applied_at) VALUES (?, 'now')",
        [(name,) for name in (
            "001_init", "002_extend_signals", "003_backfill", "012_extend_strategies",
            "013_relax_timeframe_check", "014_extend_signals_full", "015_condition_confidence",
        )],
    )

    applied = apply_migrations(conn)

    assert "011_positions_strategy_id" in applied
    assert "016_repair_signal_schema" in applied
    assert any(row[1] == "strategy_id" for row in conn.execute("PRAGMA table_info(positions)"))
