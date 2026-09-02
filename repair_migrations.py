"""Patch the live trading.db to record migrations 012 and 013 as already applied.

The DB was created from 001_init.sql (which includes 012's schema changes),
so those migrations ran but were never recorded. This script back-fills the
schema_migrations table so future runs skip them cleanly.
"""
import sqlite3, sys
from datetime import datetime, timezone

DB = "trading.db"
PATCHED_MIGRATIONS = [
    ("012_extend_strategies",      datetime.now(timezone.utc)),
    ("013_relax_timeframe_check",  datetime.now(timezone.utc)),
]

conn = sqlite3.connect(DB)
already = {r[0] for r in conn.execute("SELECT name FROM schema_migrations")}
for name, ts in PATCHED_MIGRATIONS:
    if name not in already:
        conn.execute(
            "INSERT INTO schema_migrations (name, applied_at) VALUES (?, ?)",
            (name, ts.isoformat()),
        )
        print(f"Recorded: {name}")
    else:
        print(f"Already present: {name}")
conn.commit()
conn.close()
print("Done.")
