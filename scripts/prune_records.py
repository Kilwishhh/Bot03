"""Prune operational records (signals, bot_events, errors) older than retention."""

import argparse
import sys
from pathlib import Path

from app.config import Settings
from app.database import TradingRepository


def main() -> int:
    parser = argparse.ArgumentParser(description="Prune old operational records from the trading database.")
    parser.add_argument(
        "--database-path",
        default=None,
        help="Override the database path (default: settings.database_path)",
    )
    parser.add_argument(
        "--retention-days",
        type=int,
        default=None,
        help="Override the retention window in days (default: settings.retention_days)",
    )
    args = parser.parse_args()

    settings = Settings(_env_file=None)
    db_path = args.database_path or settings.database_path
    retention_days = args.retention_days or settings.retention_days

    if not Path(db_path).exists():
        print(f"database not found: {db_path}")
        return 1

    repository = TradingRepository(db_path)
    try:
        result = repository.prune_operational_records(retention_days)
    finally:
        repository.close()

    total = sum(result.values())
    print(f"pruned {total} record(s) older than {retention_days} day(s) from {db_path}")
    for table, count in result.items():
        print(f"  {table}: {count}")
    return 0


if __name__ == "__main__":
    sys.exit(main())