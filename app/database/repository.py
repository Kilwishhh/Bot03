"""Small SQLite repository for Phase 1/2 operational records."""

import os
import sqlite3
import threading
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.exchange.models import Balance, OrderResult, Position
from app.signals.models import Signal


class TradingRepository:
    def __init__(self, database_path: str | Path | None = None) -> None:
        # check_same_thread=False because the API server runs in one thread and
        # the bot runner in another. A per-instance lock serializes all writes
        # so we don't corrupt the database or hit "objects created in a thread".
        if database_path is None:
            database_path = os.environ.get("DATABASE_PATH", "trading.db")
        self._lock = threading.RLock()
        self._connection = sqlite3.connect(
            str(database_path), check_same_thread=False, isolation_level=None
        )
        self._connection.execute("PRAGMA journal_mode=WAL")
        self._connection.execute("PRAGMA foreign_keys=ON")
        with self._lock:
            # ── legacy Phase 1/2 tables ────────────────────────────────────
            self._connection.execute("CREATE TABLE IF NOT EXISTS signals (symbol TEXT, side TEXT, confidence REAL, timestamp TEXT, strategy TEXT, reason TEXT)")
            self._connection.execute("CREATE TABLE IF NOT EXISTS orders (order_id TEXT PRIMARY KEY, symbol TEXT, status TEXT, quantity TEXT, average_price TEXT, created_at TEXT)")
            self._connection.execute("CREATE TABLE IF NOT EXISTS trades (trade_id TEXT PRIMARY KEY, symbol TEXT, side TEXT, quantity TEXT, entry_price TEXT, exit_price TEXT, realized_pnl TEXT, fees TEXT, strategy TEXT, entry_time TEXT, exit_time TEXT)")
            self._connection.execute("CREATE TABLE IF NOT EXISTS daily_pnl (trade_date TEXT PRIMARY KEY, realized_pnl TEXT, fees TEXT)")
            self._connection.execute("CREATE TABLE IF NOT EXISTS bot_events (event_id INTEGER PRIMARY KEY AUTOINCREMENT, event_type TEXT, message TEXT, created_at TEXT)")
            self._connection.execute("CREATE TABLE IF NOT EXISTS errors (error_id INTEGER PRIMARY KEY AUTOINCREMENT, error_type TEXT, message TEXT, created_at TEXT)")
            self._connection.execute("CREATE TABLE IF NOT EXISTS balances (asset TEXT PRIMARY KEY, wallet_balance TEXT, available_balance TEXT, updated_at TEXT)")
            self._connection.execute("CREATE TABLE IF NOT EXISTS positions (symbol TEXT PRIMARY KEY, side TEXT, quantity TEXT, entry_price TEXT, mark_price TEXT, leverage INTEGER, unrealized_pnl TEXT, updated_at TEXT)")
            self._connection.execute("CREATE TABLE IF NOT EXISTS control_state (id INTEGER PRIMARY KEY CHECK (id = 1), desired_state TEXT NOT NULL, heartbeat_at TEXT, updated_at TEXT NOT NULL)")

            # ── ermis multi-user tables ────────────────────────────────────
            self._connection.execute("CREATE TABLE IF NOT EXISTS users (id TEXT PRIMARY KEY, email TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL, display_name TEXT, role TEXT NOT NULL DEFAULT 'user' CHECK (role IN ('user','admin','system')), status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','suspended','deleted')), created_at TEXT NOT NULL, updated_at TEXT NOT NULL)")
            self._connection.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)")
            self._connection.execute("CREATE INDEX IF NOT EXISTS idx_users_role  ON users(role)")

            self._connection.execute("CREATE TABLE IF NOT EXISTS user_sessions (id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE, expires_at TEXT NOT NULL, created_at TEXT NOT NULL, last_used_at TEXT)")
            self._connection.execute("CREATE INDEX IF NOT EXISTS idx_sessions_user ON user_sessions(user_id)")

            self._connection.execute("CREATE TABLE IF NOT EXISTS strategies (id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE, name TEXT NOT NULL, description TEXT, version INTEGER NOT NULL DEFAULT 1, lifecycle_state TEXT NOT NULL DEFAULT 'draft' CHECK (lifecycle_state IN ('draft','backtest','paper','testnet','live_eligible','live','paused','stopped')), execution_mode TEXT NOT NULL DEFAULT 'paper' CHECK (execution_mode IN ('paper','testnet','live')), execution_venue TEXT NOT NULL DEFAULT 'binance' CHECK (execution_venue IN ('binance','hyperliquid','walletconnect')), market TEXT NOT NULL, timeframe TEXT NOT NULL DEFAULT '15m' CHECK (timeframe IN ('1m','5m','15m','1h','4h','1d')), entry_config TEXT NOT NULL DEFAULT '{}', exit_config TEXT NOT NULL DEFAULT '{}', risk_config TEXT NOT NULL DEFAULT '{}', template_name TEXT, template_params TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)")
            self._connection.execute("CREATE INDEX IF NOT EXISTS idx_strategies_user   ON strategies(user_id)")
            self._connection.execute("CREATE INDEX IF NOT EXISTS idx_strategies_state  ON strategies(lifecycle_state)")
            self._connection.execute("CREATE INDEX IF NOT EXISTS idx_strategies_market ON strategies(market)")

            self._connection.execute("CREATE TABLE IF NOT EXISTS strategy_lifecycle_events (id INTEGER PRIMARY KEY AUTOINCREMENT, strategy_id TEXT NOT NULL REFERENCES strategies(id) ON DELETE CASCADE, from_state TEXT, to_state TEXT NOT NULL, actor_user_id TEXT REFERENCES users(id) ON DELETE SET NULL, actor_role TEXT NOT NULL CHECK (actor_role IN ('user','admin','system')), reason TEXT, created_at TEXT NOT NULL)")
            self._connection.execute("CREATE INDEX IF NOT EXISTS idx_lifecycle_strategy ON strategy_lifecycle_events(strategy_id)")

            self._connection.execute("CREATE TABLE IF NOT EXISTS strategy_versions (id TEXT PRIMARY KEY, strategy_id TEXT NOT NULL REFERENCES strategies(id) ON DELETE CASCADE, version INTEGER NOT NULL, config_snapshot TEXT NOT NULL, created_at TEXT NOT NULL, UNIQUE (strategy_id, version))")

            self._connection.execute("CREATE TABLE IF NOT EXISTS backtests (id TEXT PRIMARY KEY, strategy_id TEXT NOT NULL REFERENCES strategies(id) ON DELETE CASCADE, user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE, status TEXT NOT NULL DEFAULT 'queued' CHECK (status IN ('queued','running','completed','failed')), result_summary TEXT, started_at TEXT, completed_at TEXT, error_message TEXT, created_at TEXT NOT NULL)")
            self._connection.execute("CREATE INDEX IF NOT EXISTS idx_backtests_strategy ON backtests(strategy_id)")
            self._connection.execute("CREATE INDEX IF NOT EXISTS idx_backtests_user     ON backtests(user_id)")

            self._connection.execute("CREATE TABLE IF NOT EXISTS exchange_connections (id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE, venue TEXT NOT NULL CHECK (venue IN ('binance','hyperliquid','walletconnect')), label TEXT, api_key_enc BLOB NOT NULL, api_secret_enc BLOB, wallet_address TEXT, permissions TEXT NOT NULL DEFAULT '{}', status TEXT NOT NULL DEFAULT 'connected' CHECK (status IN ('connected','disconnected','error')), created_at TEXT NOT NULL, updated_at TEXT NOT NULL)")
            self._connection.execute("CREATE INDEX IF NOT EXISTS idx_connections_user_venue ON exchange_connections(user_id, venue)")

            self._connection.execute("CREATE TABLE IF NOT EXISTS automation_rules (id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE, strategy_id TEXT REFERENCES strategies(id) ON DELETE CASCADE, name TEXT NOT NULL, trigger TEXT NOT NULL CHECK (trigger IN ('signal_generated','tp1_hit','tp2_hit','sl_hit','stop_moved','position_closed')), conditions TEXT NOT NULL DEFAULT '[]', actions TEXT NOT NULL DEFAULT '[]', enabled INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0,1)), created_at TEXT NOT NULL, updated_at TEXT NOT NULL)")
            self._connection.execute("CREATE INDEX IF NOT EXISTS idx_rules_user     ON automation_rules(user_id)")
            self._connection.execute("CREATE INDEX IF NOT EXISTS idx_rules_strategy ON automation_rules(strategy_id)")
            self._connection.execute("CREATE INDEX IF NOT EXISTS idx_rules_trigger  ON automation_rules(trigger)")

            self._connection.execute("CREATE TABLE IF NOT EXISTS automation_events (id TEXT PRIMARY KEY, rule_id TEXT NOT NULL REFERENCES automation_rules(id) ON DELETE CASCADE, signal_id TEXT, followup_id TEXT, status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','running','completed','failed','retrying')), result TEXT, attempts INTEGER NOT NULL DEFAULT 0, dedup_key TEXT NOT NULL, created_at TEXT NOT NULL, completed_at TEXT, UNIQUE (rule_id, dedup_key))")
            self._connection.execute("CREATE INDEX IF NOT EXISTS idx_auto_events_status ON automation_events(status)")

            self._connection.execute("CREATE TABLE IF NOT EXISTS publishing_configs (user_id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE, telegram_token_enc BLOB, telegram_chat_id TEXT, telegram_enabled INTEGER NOT NULL DEFAULT 0 CHECK (telegram_enabled IN (0,1)), square_api_key_enc BLOB, square_endpoint TEXT, square_daily_limit INTEGER NOT NULL DEFAULT 95, square_limit_behavior TEXT NOT NULL DEFAULT 'queue' CHECK (square_limit_behavior IN ('stop_square','telegram_only','queue')), square_enabled INTEGER NOT NULL DEFAULT 0 CHECK (square_enabled IN (0,1)), updated_at TEXT NOT NULL)")

            self._connection.execute("CREATE TABLE IF NOT EXISTS publications (id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE, signal_id TEXT, channel TEXT NOT NULL CHECK (channel IN ('telegram','binance_square')), status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','sent','failed','rate_limited','duplicate')), posted_at TEXT, error_message TEXT, dedup_key TEXT NOT NULL, created_at TEXT NOT NULL, UNIQUE (user_id, channel, dedup_key))")
            self._connection.execute("CREATE INDEX IF NOT EXISTS idx_publications_user ON publications(user_id, created_at DESC)")

            self._connection.execute("CREATE TABLE IF NOT EXISTS emergency_pauses (id TEXT PRIMARY KEY, scope TEXT NOT NULL CHECK (scope IN ('strategy','user','integration','platform')), scope_target TEXT, actor_user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE, actor_role TEXT NOT NULL CHECK (actor_role IN ('user','admin','system')), reason TEXT NOT NULL, close_positions INTEGER NOT NULL DEFAULT 0 CHECK (close_positions IN (0,1)), created_at TEXT NOT NULL, expires_at TEXT, resumed_at TEXT)")
            self._connection.execute("CREATE INDEX IF NOT EXISTS idx_pauses_scope ON emergency_pauses(scope, scope_target)")
            self._connection.execute("CREATE TABLE IF NOT EXISTS audit_log (id INTEGER PRIMARY KEY AUTOINCREMENT, actor_user_id TEXT REFERENCES users(id) ON DELETE SET NULL, actor_role TEXT NOT NULL, action TEXT NOT NULL, target_type TEXT, target_id TEXT, detail TEXT, result TEXT NOT NULL CHECK (result IN ('ok','rejected','error')), created_at TEXT NOT NULL)")
            self._connection.execute("CREATE INDEX IF NOT EXISTS idx_audit_actor  ON audit_log(actor_user_id, created_at DESC)")
            self._connection.execute("CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_log(action, created_at DESC)")
            self._connection.execute("CREATE INDEX IF NOT EXISTS idx_audit_target ON audit_log(target_type, target_id)")

    def save_signal(self, signal: Signal) -> None:
        with self._lock:
            self._connection.execute(
                "INSERT INTO signals VALUES (?, ?, ?, ?, ?, ?)",
                (signal.symbol, signal.side.value, signal.confidence, signal.timestamp.isoformat(), signal.strategy_name, "; ".join(signal.reason)),
            )

    def save_order(self, order: OrderResult) -> None:
        with self._lock:
            self._connection.execute(
                "INSERT OR REPLACE INTO orders VALUES (?, ?, ?, ?, ?, ?)",
                (order.order_id, order.symbol, order.status, str(order.executed_quantity), str(order.average_price) if order.average_price is not None else None, datetime.now(UTC).isoformat()),
            )

    def count(self, table: str) -> int:
        if table not in {"signals", "orders", "trades", "daily_pnl", "bot_events", "errors", "balances", "positions"}:
            raise ValueError("unsupported table")
        with self._lock:
            return int(self._connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])

    def record_event(self, event_type: str, message: str) -> None:
        with self._lock:
            self._connection.execute(
                "INSERT INTO bot_events (event_type, message, created_at) VALUES (?, ?, ?)",
                (event_type, message, datetime.now(UTC).isoformat()),
            )

    def record_error(self, error_type: str, message: str) -> None:
        with self._lock:
            self._connection.execute(
                "INSERT INTO errors (error_type, message, created_at) VALUES (?, ?, ?)",
                (error_type, message, datetime.now(UTC).isoformat()),
            )

    def save_balance(self, balance: Balance) -> None:
        with self._lock:
            self._connection.execute(
                "INSERT OR REPLACE INTO balances VALUES (?, ?, ?, ?)",
                (balance.asset, str(balance.wallet_balance), str(balance.available_balance), datetime.now(UTC).isoformat()),
            )

    def save_position(self, position: Position | None) -> None:
        if position is None:
            return
        with self._lock:
            self._connection.execute(
                "INSERT OR REPLACE INTO positions VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (position.symbol, position.side.value, str(position.quantity), str(position.entry_price), str(position.mark_price), position.leverage, str(position.unrealized_pnl), datetime.now(UTC).isoformat()),
            )

    def recent_orders(self, limit: int = 20) -> list[tuple]:
        with self._lock:
            return self._connection.execute(
                "SELECT order_id, symbol, status, quantity, average_price, created_at FROM orders ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()

    def recent_trades(self, limit: int = 20) -> list[tuple]:
        with self._lock:
            return self._connection.execute(
                "SELECT trade_id, symbol, side, quantity, entry_price, exit_price, realized_pnl, fees, strategy, entry_time, exit_time FROM trades ORDER BY exit_time DESC LIMIT ?",
                (limit,),
            ).fetchall()

    def balances(self) -> list[tuple]:
        with self._lock:
            return self._connection.execute("SELECT asset, wallet_balance, available_balance, updated_at FROM balances ORDER BY asset").fetchall()

    def positions(self) -> list[tuple]:
        with self._lock:
            return self._connection.execute("SELECT symbol, side, quantity, entry_price, mark_price, leverage, unrealized_pnl, updated_at FROM positions ORDER BY symbol").fetchall()

    def recent_events(self, limit: int = 20) -> list[tuple]:
        with self._lock:
            return self._connection.execute(
                "SELECT event_type, message, created_at FROM bot_events ORDER BY event_id DESC LIMIT ?",
                (limit,),
            ).fetchall()

    def recent_errors(self, limit: int = 20) -> list[tuple]:
        with self._lock:
            return self._connection.execute(
                "SELECT error_type, message, created_at FROM errors ORDER BY error_id DESC LIMIT ?",
                (limit,),
            ).fetchall()

    def set_control_state(self, desired_state: str, heartbeat_at: str | None = None) -> None:
        now = datetime.now(UTC).isoformat()
        with self._lock:
            self._connection.execute(
                "INSERT INTO control_state (id, desired_state, heartbeat_at, updated_at) VALUES (1, ?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET desired_state = ?, heartbeat_at = ?, updated_at = ?",
                (desired_state, heartbeat_at, now, desired_state, heartbeat_at, now),
            )

    def control_state(self) -> tuple[str, str | None, str] | None:
        with self._lock:
            return self._connection.execute("SELECT desired_state, heartbeat_at, updated_at FROM control_state WHERE id = 1").fetchone()

    def prune_operational_records(self, retention_days: int) -> dict[str, int]:
        cutoff = (datetime.now(UTC) - timedelta(days=retention_days)).isoformat()
        deleted = {}
        with self._lock:
            for table, column in (("signals", "timestamp"), ("bot_events", "created_at"), ("errors", "created_at")):
                cursor = self._connection.execute(f"DELETE FROM {table} WHERE {column} < ?", (cutoff,))
                deleted[table] = cursor.rowcount
        return deleted

    def save_trade(self, trade: dict[str, str]) -> None:
        with self._lock:
            self._connection.execute(
                "INSERT OR REPLACE INTO trades VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                tuple(trade[key] for key in ("trade_id", "symbol", "side", "quantity", "entry_price", "exit_price", "realized_pnl", "fees", "strategy", "entry_time", "exit_time")),
            )

    def record_daily_pnl(self, trade_date: str, realized_pnl: str, fees: str) -> None:
        with self._lock:
            self._connection.execute(
                "INSERT INTO daily_pnl (trade_date, realized_pnl, fees) VALUES (?, ?, ?) "
                "ON CONFLICT(trade_date) DO UPDATE SET realized_pnl = ?, fees = ?",
                (trade_date, realized_pnl, fees, realized_pnl, fees),
            )

    def record_audit(
        self, *, actor_user_id: str | None, actor_role: str, action: str,
        result: str = "ok", target_type: str | None = None, target_id: str | None = None,
        detail: str | None = None,
    ) -> int:
        with self._lock:
            cur = self._connection.execute(
                "INSERT INTO audit_log (actor_user_id, actor_role, action, "
                "target_type, target_id, detail, result, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (actor_user_id, actor_role, action, target_type, target_id,
                 detail, result, datetime.now(UTC).isoformat()),
            )
            return int(cur.lastrowid or 0)

    def recent_audit(self, limit: int = 50, actor_user_id: str | None = None,
                     action: str | None = None) -> list[tuple]:
        with self._lock:
            q = ("SELECT id, actor_user_id, actor_role, action, target_type, target_id, "
                 "detail, result, created_at FROM audit_log WHERE 1=1")
            params: list = []
            if actor_user_id:
                q += " AND actor_user_id = ?"
                params.append(actor_user_id)
            if action:
                q += " AND action = ?"
                params.append(action)
            q += " ORDER BY id DESC LIMIT ?"
            params.append(limit)
            return self._connection.execute(q, params).fetchall()

    def close(self) -> None:
        with self._lock:
            self._connection.close()


_default_repo: "TradingRepository | None" = None


def _default() -> "TradingRepository":
    global _default_repo
    if _default_repo is None:
        _default_repo = TradingRepository()
    return _default_repo


def get_default_repository() -> "TradingRepository":
    return _default()
