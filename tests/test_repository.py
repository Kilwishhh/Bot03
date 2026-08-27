from datetime import UTC, datetime
from decimal import Decimal

from app.database import TradingRepository
from app.exchange.models import Balance, OrderResult, OrderSide, Position
from app.signals import Signal, SignalSide


def test_repository_persists_signals_and_orders(tmp_path):
    repository = TradingRepository(tmp_path / "trading.sqlite3")
    repository.save_signal(Signal("BTCUSDT", SignalSide.HOLD, 0.0, datetime.now(UTC)))
    repository.save_order(OrderResult("order-1", "BTCUSDT", "FILLED", Decimal("1"), Decimal("100")))
    repository.save_trade({
        "trade_id": "trade-1", "symbol": "BTCUSDT", "side": "BUY", "quantity": "1",
        "entry_price": "100", "exit_price": "110", "realized_pnl": "10", "fees": "1",
        "strategy": "demo", "entry_time": "2026-08-25T00:00:00+00:00", "exit_time": "2026-08-25T01:00:00+00:00",
    })
    repository.record_daily_pnl("2026-08-25", "10", "1")
    repository.record_event("bot_started", "paper mode")
    repository.record_error("api", "temporary failure")
    repository.save_balance(Balance("USDT", Decimal("1000"), Decimal("900")))
    repository.save_position(Position("BTCUSDT", OrderSide.BUY, Decimal("1"), Decimal("100"), Decimal("101"), 1))
    assert repository.count("signals") == 1
    assert repository.count("orders") == 1
    assert repository.count("trades") == 1
    assert repository.count("daily_pnl") == 1
    assert repository.count("bot_events") == 1
    assert repository.count("errors") == 1
    assert repository.count("balances") == 1
    assert repository.count("positions") == 1
    repository.close()
