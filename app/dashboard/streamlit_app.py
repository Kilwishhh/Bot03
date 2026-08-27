"""Optional local dashboard for SQLite trading records (Phase 4 observability)."""

import sqlite3
from pathlib import Path


def load_counts(database_path: str | Path = "trading.db") -> dict[str, int]:
    connection = sqlite3.connect(database_path)
    try:
        return {
            table: int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
            for table in ("signals", "orders", "trades", "daily_pnl", "bot_events", "errors", "balances", "positions")
            if connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()
        }
    finally:
        connection.close()


def load_recent_orders(database_path: str | Path = "trading.db", limit: int = 20) -> list[tuple]:
    connection = sqlite3.connect(database_path)
    try:
        return connection.execute(
            "SELECT order_id, symbol, status, quantity, average_price, created_at FROM orders ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    finally:
        connection.close()


def load_recent_signals(database_path: str | Path = "trading.db", limit: int = 20) -> list[tuple]:
    connection = sqlite3.connect(database_path)
    try:
        return connection.execute(
            "SELECT symbol, side, confidence, timestamp, strategy, reason FROM signals ORDER BY timestamp DESC LIMIT ?",
            (limit,),
        ).fetchall()
    finally:
        connection.close()


def load_open_positions(database_path: str | Path = "trading.db") -> list[tuple]:
    connection = sqlite3.connect(database_path)
    try:
        return connection.execute(
            "SELECT symbol, side, quantity, entry_price, mark_price, leverage, unrealized_pnl, updated_at FROM positions ORDER BY symbol"
        ).fetchall()
    finally:
        connection.close()


def load_balances(database_path: str | Path = "trading.db") -> list[tuple]:
    connection = sqlite3.connect(database_path)
    try:
        return connection.execute(
            "SELECT asset, wallet_balance, available_balance, updated_at FROM balances ORDER BY asset"
        ).fetchall()
    finally:
        connection.close()


def load_daily_pnl(database_path: str | Path = "trading.db", limit: int = 30) -> list[tuple]:
    connection = sqlite3.connect(database_path)
    try:
        return connection.execute(
            "SELECT trade_date, realized_pnl, fees FROM daily_pnl ORDER BY trade_date DESC LIMIT ?",
            (limit,),
        ).fetchall()
    finally:
        connection.close()


def load_recent_events(database_path: str | Path = "trading.db", limit: int = 20) -> list[tuple]:
    connection = sqlite3.connect(database_path)
    try:
        return connection.execute(
            "SELECT event_type, message, created_at FROM bot_events ORDER BY event_id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    finally:
        connection.close()


def load_recent_errors(database_path: str | Path = "trading.db", limit: int = 20) -> list[tuple]:
    connection = sqlite3.connect(database_path)
    try:
        return connection.execute(
            "SELECT error_type, message, created_at FROM errors ORDER BY error_id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    finally:
        connection.close()


def main() -> None:
    import streamlit as st

    st.set_page_config(page_title="MK Trader Dashboard", layout="wide", page_icon="📈")
    st.title("MK Trader — Trading Dashboard")
    st.caption("Paper/Testnet monitoring only. Performance not yet validated.")

    db_path = st.sidebar.text_input("Database path", value="trading.db")
    st.sidebar.markdown("---")

    try:
        counts = load_counts(db_path)
    except Exception as error:
        st.error(f"Cannot read database: {error}")
        return

    cols = st.columns(4)
    for col, table in zip(cols, ("signals", "orders", "trades", "daily_pnl"), strict=False):
        col.metric(table.replace("_", " ").title(), counts.get(table, 0))

    st.caption(
        f"Balances: {counts.get('balances', 0)} | Positions: {counts.get('positions', 0)} | "
        f"Errors: {counts.get('errors', 0)} | Events: {counts.get('bot_events', 0)}"
    )

    st.subheader("Recent orders")
    try:
        st.dataframe(load_recent_orders(db_path, 20), use_container_width=True)
    except Exception as error:
        st.warning(f"Orders unavailable: {error}")

    st.subheader("Recent signals")
    try:
        st.dataframe(load_recent_signals(db_path, 20), use_container_width=True)
    except Exception as error:
        st.warning(f"Signals unavailable: {error}")

    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("Open positions")
        try:
            st.dataframe(load_open_positions(db_path), use_container_width=True)
        except Exception as error:
            st.warning(f"Positions unavailable: {error}")
    with col_b:
        st.subheader("Balances")
        try:
            st.dataframe(load_balances(db_path), use_container_width=True)
        except Exception as error:
            st.warning(f"Balances unavailable: {error}")

    st.subheader("Daily PnL (last 30 days)")
    try:
        st.dataframe(load_daily_pnl(db_path, 30), use_container_width=True)
    except Exception as error:
        st.warning(f"Daily PnL unavailable: {error}")

    st.subheader("Recent events")
    try:
        st.dataframe(load_recent_events(db_path, 20), use_container_width=True)
    except Exception as error:
        st.warning(f"Events unavailable: {error}")

    st.subheader("Recent errors")
    try:
        st.dataframe(load_recent_errors(db_path, 20), use_container_width=True)
    except Exception as error:
        st.warning(f"Errors unavailable: {error}")

    st.markdown("---")
    st.caption("MK Trader v0.1.0 · Paper/Testnet monitoring only · Live execution disabled by default")


if __name__ == "__main__":
    main()
