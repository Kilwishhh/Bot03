"""Seed the SIGNAL_PIPELINE_TEST diagnostic strategy.

PAPER ONLY — refuses testnet/live transitions.

ALWAYS_TRUE condition emits a signal for every fresh 1m candle.
1m cooldown (1 signal per symbol per candle) is enforced by the scanner dedup.
"""
from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path
import os


def _conn(repo=None):
    if repo is not None:
        return repo.db
    db_path = os.environ.get("DATABASE_PATH", "trading.db")
    return sqlite3.connect(db_path, check_same_thread=False, isolation_level=None)


def seed(force: bool = False, repo=None) -> str:
    """Create the SIGNAL_PIPELINE_TEST strategy if it doesn't exist.

    If `repo` is provided, uses repo.db (useful for tests with custom DB paths).
    Returns the strategy id. If it already exists and force=False, returns
    the existing id without modifications.
    """
    conn = _conn(repo)
    try:
        row = conn.execute(
            "SELECT id FROM strategies WHERE name = 'SIGNAL_PIPELINE_TEST' LIMIT 1"
        ).fetchone()
        if row and not force:
            return row[0]

        # Find a system/admin user_id (use the first admin or system user)
        u = conn.execute(
            "SELECT id FROM users WHERE role IN ('admin','system') ORDER BY created_at ASC LIMIT 1"
        ).fetchone()
        if not u:
            # Create a system user as a fallback
            uid = str(uuid.uuid4())
            now = datetime.now(UTC).isoformat()
            conn.execute(
                "INSERT INTO users (id, email, password_hash, display_name, role, status, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (uid, "system@mktrader.local", "!", "System", "system", "active", now, now),
            )
            user_id = uid
        else:
            user_id = u[0]

        now = datetime.now(UTC).isoformat()
        if row and force:
            sid = row[0]
            conn.execute(
                "UPDATE strategies SET user_id=?, description=?, version=version+1, "
                "lifecycle_state=?, execution_mode=?, execution_venue=?, market=?, "
                "timeframe=?, entry_config=?, exit_config=?, risk_config=?, "
                "universe_type=?, universe_config=?, indicators_config=?, "
                "conditions_config=?, filters_config=?, confidence_config=?, "
                "notes=?, updated_at=? WHERE id=?",
                (
                    user_id,
                    "SYSTEM DIAGNOSTIC — verifies end-to-end signal pipeline. Paper only. Do not promote to TESTNET/LIVE.",
                    "paper",
                    "paper",
                    "binance",
                    "binance_futures",
                    "1m",
                    json.dumps({}),
                    json.dumps({"take_profit_pct": 1.0, "stop_loss_pct": 0.5}),
                    json.dumps({}),
                    "all_binance_futures",
                    json.dumps({}),
                    json.dumps([]),
                    json.dumps({
                        "logic": "all",
                        "groups": [
                            {
                                "logic": "all",
                                "conditions": [
                                    {"field": "PRICE", "op": ">", "value": 0}
                                ],
                            }
                        ],
                    }),
                    json.dumps({}),
                    json.dumps({"mode": "fixed", "min_confidence": 0.5}),
                    "SYSTEM DIAGNOSTIC — paper-only. Refuses testnet/live.",
                    now,
                    sid,
                ),
            )
        else:
            sid = str(uuid.uuid4())
            conn.execute(
                "INSERT INTO strategies (id, user_id, name, description, version, "
                "lifecycle_state, execution_mode, execution_venue, market, timeframe, "
                "entry_config, exit_config, risk_config, template_name, template_params, "
                "created_at, updated_at, universe_type, universe_config, "
                "indicators_config, conditions_config, filters_config, "
                "confidence_config, notes) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    sid,
                    user_id,
                    "SIGNAL_PIPELINE_TEST",
                    "SYSTEM DIAGNOSTIC — verifies end-to-end signal pipeline. Paper only. Do not promote to TESTNET/LIVE.",
                    1,
                    "paper",
                    "paper",
                    "binance",
                    "binance_futures",
                    "1m",
                    json.dumps({}),
                    json.dumps({"take_profit_pct": 1.0, "stop_loss_pct": 0.5}),
                    json.dumps({}),
                    None,
                    json.dumps({}),
                    now,
                    now,
                    "all_binance_futures",
                    json.dumps({}),
                    json.dumps([]),
                    json.dumps({
                        "logic": "all",
                        "groups": [
                            {
                                "logic": "all",
                                "conditions": [
                                    {"field": "PRICE", "op": ">", "value": 0}
                                ],
                            }
                        ],
                    }),
                    json.dumps({}),
                    json.dumps({"mode": "fixed", "min_confidence": 0.5}),
                    "SYSTEM DIAGNOSTIC — paper-only. Refuses testnet/live.",
                ),
            )

        # Audit lifecycle event
        try:
            conn.execute(
                "INSERT INTO strategy_lifecycle_events "
                "(strategy_id, from_state, to_state, actor_user_id, actor_role, reason, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (sid, "draft", "paper", "system", "system", "seeded by signal_pipeline_test", now),
            )
        except Exception:
            pass

        return sid
    finally:
        conn.close()


if __name__ == "__main__":
    print(seed())
