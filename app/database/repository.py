"""Small SQLite repository for Phase 1/2 operational records."""

import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.exchange.models import Balance, OrderResult, Position
from app.signals.models import Signal


class TradingRepository:
    def __init__(self, database_path: str | Path = "trading.db") -> None:
        self._connection = sqlite3.connect(database_path)
        self._connection.execute("CREATE TABLE IF NOT EXISTS signals (symbol TEXT, side TEXT, confidence REAL, timestamp TEXT, strategy TEXT, reason TEXT)")
        self._connection.execute("CREATE TABLE IF NOT EXISTS orders (order_id TEXT PRIMARY KEY, symbol TEXT, status TEXT, quantity TEXT, average_price TEXT, created_at TEXT)")
        self._connection.execute("CREATE TABLE IF NOT EXISTS trades (trade_id TEXT PRIMARY KEY, symbol TEXT, side TEXT, quantity TEXT, entry_price TEXT, exit_price TEXT, realized_pnl TEXT, fees TEXT, strategy TEXT, entry_time TEXT, exit_time TEXT)")
        self._connection.execute("CREATE TABLE IF NOT EXISTS daily_pnl (trade_date TEXT PRIMARY KEY, realized_pnl TEXT, fees TEXT)")
        self._connection.execute("CREATE TABLE IF NOT EXISTS bot_events (event_id INTEGER PRIMARY KEY AUTOINCREMENT, event_type TEXT, message TEXT, created_at TEXT)")
        self._connection.execute("CREATE TABLE IF NOT EXISTS errors (error_id INTEGER PRIMARY KEY AUTOINCREMENT, error_type TEXT, message TEXT, created_at TEXT)")
        self._connection.execute("CREATE TABLE IF NOT EXISTS balances (asset TEXT PRIMARY KEY, wallet_balance TEXT, available_balance TEXT, updated_at TEXT)")
        self._connection.execute("CREATE TABLE IF NOT EXISTS positions (symbol TEXT PRIMARY KEY, side TEXT, quantity TEXT, entry_price TEXT, mark_price TEXT, leverage INTEGER, unrealized_pnl TEXT, updated_at TEXT)")
        self._connection.execute("CREATE TABLE IF NOT EXISTS control_state (id INTEGER PRIMARY KEY CHECK (id = 1), desired_state TEXT NOT NULL, heartbeat_at TEXT, updated_at TEXT NOT NULL)")
        self._connection.commit()

    def save_signal(self, signal: Signal) -> None:
        self._connection.execute(
            "INSERT INTO signals VALUES (?, ?, ?, ?, ?, ?)",
            (signal.symbol, signal.side.value, signal.confidence, signal.timestamp.isoformat(), signal.strategy_name, "; ".join(signal.reason)),
        )
        self._connection.commit()

    def save_order(self, order: OrderResult) -> None:
        self._connection.execute(
            "INSERT OR REPLACE INTO orders VALUES (?, ?, ?, ?, ?, ?)",
            (order.order_id, order.symbol, order.status, str(order.executed_quantity), str(order.average_price) if order.average_price is not None else None, datetime.now(UTC).isoformat()),
        )
        self._connection.commit()

    def count(self, table: str) -> int:
        if table not in {"signals", "orders", "trades", "daily_pnl", "bot_events", "errors", "balances", "positions"}:
            raise ValueError("unsupported table")
        return int(self._connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])

    def record_event(self, event_type: str, message: str) -> None:
        self._connection.execute(
            "INSERT INTO bot_events (event_type, message, created_at) VALUES (?, ?, ?)",
            (event_type, message, datetime.now(UTC).isoformat()),
        )
        self._connection.commit()

    def record_error(self, error_type: str, message: str) -> None:
        self._connection.execute(
            "INSERT INTO errors (error_type, message, created_at) VALUES (?, ?, ?)",
            (error_type, message, datetime.now(UTC).isoformat()),
        )
        self._connection.commit()

    def save_balance(self, balance: Balance) -> None:
        self._connection.execute(
            "INSERT OR REPLACE INTO balances VALUES (?, ?, ?, ?)",
            (balance.asset, str(balance.wallet_balance), str(balance.available_balance), datetime.now(UTC).isoformat()),
        )
        self._connection.commit()

    def save_position(self, position: Position | None) -> None:
        if position is None:
            return
        self._connection.execute(
            "INSERT OR REPLACE INTO positions VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (position.symbol, position.side.value, str(position.quantity), str(position.entry_price), str(position.mark_price), position.leverage, str(position.unrealized_pnl), datetime.now(UTC).isoformat()),
        )
        self._connection.commit()

    def recent_orders(self, limit: int = 20) -> list[tuple]:
        return self._connection.execute(
            "SELECT order_id, symbol, status, quantity, average_price, created_at FROM orders ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()

    def recent_trades(self, limit: int = 20) -> list[tuple]:
        return self._connection.execute(
            "SELECT trade_id, symbol, side, quantity, entry_price, exit_price, realized_pnl, fees, strategy, entry_time, exit_time FROM trades ORDER BY exit_time DESC LIMIT ?",
            (limit,),
        ).fetchall()

    def balances(self) -> list[tuple]:
        return self._connection.execute("SELECT asset, wallet_balance, available_balance, updated_at FROM balances ORDER BY asset").fetchall()

    def positions(self) -> list[tuple]:
        return self._connection.execute("SELECT symbol, side, quantity, entry_price, mark_price, leverage, unrealized_pnl, updated_at FROM positions ORDER BY symbol").fetchall()

    def recent_events(self, limit: int = 20) -> list[tuple]:
        return self._connection.execute(
            "SELECT event_type, message, created_at FROM bot_events ORDER BY event_id DESC LIMIT ?",
            (limit,),
        ).fetchall()

    def recent_errors(self, limit: int = 20) -> list[tuple]:
        return self._connection.execute(
            "SELECT error_type, message, created_at FROM errors ORDER BY error_id DESC LIMIT ?",
            (limit,),
        ).fetchall()

    def set_control_state(self, desired_state: str, heartbeat_at: str | None = None) -> None:
        now = datetime.now(UTC).isoformat()
        self._connection.execute(
            "INSERT INTO control_state (id, desired_state, heartbeat_at, updated_at) VALUES (1, ?, ?, ?) "
            "ON CONFLICT(id) DO UPDATE SET desired_state = ?, heartbeat_at = ?, updated_at = ?",
            (desired_state, heartbeat_at, now, desired_state, heartbeat_at, now),
        )
        self._connection.commit()

    def control_state(self) -> tuple[str, str | None, str] | None:
        return self._connection.execute("SELECT desired_state, heartbeat_at, updated_at FROM control_state WHERE id = 1").fetchone()

    def prune_operational_records(self, retention_days: int) -> dict[str, int]:
        cutoff = (datetime.now(UTC) - timedelta(days=retention_days)).isoformat()
        deleted = {}
        for table, column in (("signals", "timestamp"), ("bot_events", "created_at"), ("errors", "created_at")):
            cursor = self._connection.execute(f"DELETE FROM {table} WHERE {column} < ?", (cutoff,))
            deleted[table] = cursor.rowcount
        self._connection.commit()
        return deleted

    def save_trade(self, trade: dict[str, str]) -> None:
        self._connection.execute(
            "INSERT OR REPLACE INTO trades VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            tuple(trade[key] for key in ("trade_id", "symbol", "side", "quantity", "entry_price", "exit_price", "realized_pnl", "fees", "strategy", "entry_time", "exit_time")),
        )
        self._connection.commit()

    def record_daily_pnl(self, trade_date: str, realized_pnl: str, fees: str) -> None:
        self._connection.execute(
            "INSERT INTO daily_pnl (trade_date, realized_pnl, fees) VALUES (?, ?, ?) "
            "ON CONFLICT(trade_date) DO UPDATE SET realized_pnl = ?, fees = ?",
            (trade_date, realized_pnl, fees, realized_pnl, fees),
        )
        self._connection.commit()

    def close(self) -> None:
        self._connection.close()
