"""Ordered list of migration names. Each entry must have a matching
`app/database/migrations/<name>.sql` file with idempotent DDL/DML.
"""

MIGRATIONS: list[str] = [
    "001_init",
    "002_extend_signals",
    "003_backfill",
]
