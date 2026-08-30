"""Seed the RSI Reversion 1M Test strategy — STRATEGY-TEST-001.

Idempotent. Safe to run multiple times. Creates:
  * Test user test@local.dev (if missing)
  * Strategy "RSI Reversion 1M Test" in PAPER state
  * 3 default automation rules (signal, tp1, sl)
  * Publishing config (telegram off, square 10/day, telegram_only on limit)

Run:
    python -m app.seed.rsi_reversion_test
"""

from __future__ import annotations

import json
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

# Allow running as a script
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.core.auth import hash_password
from app.core.rbac import AccessContext
from app.domain.connection import SquareLimitBehavior
from app.domain.strategy import (
    EntryConfig,
    ExecutionMode,
    ExecutionVenue,
    ExitConfig,
    LifecycleState,
    RiskConfig,
    Timeframe,
)
from app.domain.user import User, UserRole, UserStatus
from app.services.strategy_service import StrategyService

TEST_EMAIL = "test@local.dev"
TEST_PASSWORD = "testpass123"
TEST_DISPLAY = "Test User"
STRATEGY_NAME = "RSI Reversion 1M Test"
STRATEGY_DESC = "Mean-reversion on RSI(14) oversold/overbought, 1m timeframe, paper-only fixture"
TEMPLATE_NAME = "rsi_reversion_1m_test"
# Canonical UUID used by test files so hardcoded IDs in tests always find this strategy
CANONICAL_STRATEGY_ID = "47ddb081-d9bb-454d-bc67-f715d96ef6c4"
DB_PATH = "trading.db"


def _get_or_create_test_user() -> User:
    import sqlite3
    conn = sqlite3.connect(DB_PATH)
    try:
        row = conn.execute(
            "SELECT id, email, password_hash, display_name, role, status, created_at, updated_at "
            "FROM users WHERE email = ?", (TEST_EMAIL,)).fetchone()
        if row:
            role = UserRole(row[4]) if row[4] in {"user", "admin", "system"} else UserRole.USER
            status = UserStatus(row[5]) if row[5] in {"active", "suspended", "deleted"} else UserStatus.ACTIVE
            return User(
                id=row[0], email=row[1], password_hash=row[2], display_name=row[3],
                role=role, status=status,
                created_at=datetime.fromisoformat(row[6]), updated_at=datetime.fromisoformat(row[7]),
            )
        user_id = str(uuid.uuid4())
        now = datetime.now(UTC).isoformat()
        conn.execute(
            "INSERT INTO users (id, email, password_hash, display_name, role, status, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (user_id, TEST_EMAIL, hash_password(TEST_PASSWORD), TEST_DISPLAY,
             UserRole.USER.value, UserStatus.ACTIVE.value, now, now),
        )
        # Audit the registration
        conn.execute(
            "INSERT INTO audit_log (actor_user_id, actor_role, action, target_type, target_id, detail, result, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (None, "system", "user.register", "user", user_id,
             json.dumps({"source": "seed:rsi_reversion_test", "email": TEST_EMAIL}),
             "ok", now),
        )
        conn.commit()
        return User(
            id=user_id, email=TEST_EMAIL, password_hash=hash_password(TEST_PASSWORD),
            display_name=TEST_DISPLAY, role=UserRole.USER, status=UserStatus.ACTIVE,
            created_at=datetime.fromisoformat(now), updated_at=datetime.fromisoformat(now),
        )
    finally:
        conn.close()


def _get_existing_strategy_id(user_id: str) -> str | None:
    import sqlite3
    conn = sqlite3.connect(DB_PATH)
    try:
        row = conn.execute(
            "SELECT id FROM strategies WHERE user_id = ? AND name = ?",
            (user_id, STRATEGY_NAME)).fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def _get_or_create_strategy(user: User) -> str:
    # First check if a strategy with the canonical ID already exists (idempotent reseed)
    import sqlite3
    _conn = sqlite3.connect(DB_PATH)
    try:
        existing = _conn.execute(
            "SELECT id FROM strategies WHERE id = ?", (CANONICAL_STRATEGY_ID,)).fetchone()
        if existing:
            return existing[0]
    finally:
        _conn.close()

    # Use a direct INSERT (bypassing StrategyService which auto-generates a UUID)
    # so the canonical test ID is preserved.
    now = datetime.now(UTC).isoformat()
    entry_cfg = json.dumps({
        "indicators": [{"name": "rsi", "period": 14, "source": "close"}],
        "conditions": [
            {"indicator": "rsi", "op": "<=", "value": 30, "then": "long"},
            {"indicator": "rsi", "op": ">=", "value": 70, "then": "short"},
        ],
        "template": TEMPLATE_NAME,
    })
    exit_cfg = json.dumps({"tp1_pct": 0.003, "tp2_pct": 0.0,
                           "stop_loss_pct": 0.005, "trailing_stop": False})
    risk_cfg = json.dumps({"max_per_trade": 0.01, "max_daily_loss": 0.05,
                           "max_open_positions": 3, "max_leverage": 10,
                           "max_exposure": 0.5})
    template_params = json.dumps({
        "rsi_period": 14, "rsi_oversold": 30, "rsi_overbought": 70,
        "tp1_pct": 0.003, "stop_loss_pct": 0.005, "cooldown_seconds": 180,
        "symbols": ["BTCUSDT", "ETHUSDT", "SOLUSDT"],
    })

    _conn = sqlite3.connect(DB_PATH)
    try:
        _conn.execute(
            "INSERT OR REPLACE INTO strategies "
            "(id, user_id, name, description, version, lifecycle_state, execution_mode, "
            " execution_venue, market, timeframe, entry_config, exit_config, risk_config, "
            " template_name, template_params, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (CANONICAL_STRATEGY_ID, user.id, STRATEGY_NAME, STRATEGY_DESC, 1,
             LifecycleState.PAPER.value, ExecutionMode.PAPER.value,
             ExecutionVenue.BINANCE.value, "BTCUSDT", Timeframe.M1.value,
             entry_cfg, exit_cfg, risk_cfg, TEMPLATE_NAME, template_params, now, now),
        )
        _conn.execute(
            "INSERT OR REPLACE INTO strategy_lifecycle_events "
            "(id, strategy_id, from_state, to_state, actor_user_id, actor_role, reason, created_at) "
            "VALUES (?, ?, NULL, ?, ?, ?, ?, ?)",
            (None, CANONICAL_STRATEGY_ID, LifecycleState.PAPER.value,
             user.id, "system", "seeded", now),
        )
        _conn.commit()
        return CANONICAL_STRATEGY_ID
    finally:
        _conn.close()


def _seed_publishing_config(user: User) -> None:
    import sqlite3
    conn = sqlite3.connect(DB_PATH)
    try:
        row = conn.execute(
            "SELECT user_id FROM publishing_configs WHERE user_id = ?", (user.id,)).fetchone()
        if row:
            return
        now = datetime.now(UTC).isoformat()
        conn.execute(
            "INSERT INTO publishing_configs "
            "(user_id, telegram_token_enc, telegram_chat_id, telegram_enabled, "
            " square_api_key_enc, square_endpoint, square_daily_limit, "
            " square_limit_behavior, square_enabled, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (user.id, None, None, 0, None, None, 10,
             SquareLimitBehavior.TELEGRAM_ONLY.value, 1, now),
        )
        conn.commit()
    finally:
        conn.close()


def _seed_automation_rules(user: User, strategy_id: str) -> list[str]:
    import sqlite3
    conn = sqlite3.connect(DB_PATH)
    try:
        existing = [
            r[0] for r in conn.execute(
                "SELECT id FROM automation_rules WHERE strategy_id = ? AND user_id = ?",
                (strategy_id, user.id)).fetchall()
        ]
        if len(existing) >= 3:
            return existing

        now = datetime.now(UTC).isoformat()
        created: list[str] = []
        rules = [
            {
                "name": "RSI Signal: create paper trade + publish",
                "trigger": "signal_generated",
                "actions": [
                    {"type": "create_paper_trade"},
                    {"type": "publish_telegram"},
                    {"type": "publish_square"},
                ],
            },
            {
                "name": "RSI TP1 hit: followup + telegram",
                "trigger": "tp1_hit",
                "actions": [
                    {"type": "create_followup"},
                    {"type": "publish_telegram"},
                ],
            },
            {
                "name": "RSI SL hit: followup + telegram",
                "trigger": "sl_hit",
                "actions": [
                    {"type": "create_followup"},
                    {"type": "publish_telegram"},
                ],
            },
        ]
        for r in rules:
            rid = str(uuid.uuid4())
            conn.execute(
                "INSERT INTO automation_rules VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (rid, user.id, strategy_id, r["name"], r["trigger"],
                 json.dumps([]), json.dumps(r["actions"]), 1, now, now),
            )
            created.append(rid)
        conn.commit()
        return created
    finally:
        conn.close()


def run() -> dict:
    user = _get_or_create_test_user()
    strategy_id = _get_or_create_strategy(user)
    _seed_publishing_config(user)
    rule_ids = _seed_automation_rules(user, strategy_id)
    return {
        "user_id": user.id,
        "user_email": user.email,
        "user_password": TEST_PASSWORD,
        "strategy_id": strategy_id,
        "rule_ids": rule_ids,
        "lifecycle_state": LifecycleState.PAPER.value,
        "execution_mode": ExecutionMode.PAPER.value,
        "timeframe": Timeframe.M1.value,
        "symbols": ["BTCUSDT", "ETHUSDT", "SOLUSDT"],
    }


if __name__ == "__main__":
    result = run()
    print(json.dumps(result, indent=2))
