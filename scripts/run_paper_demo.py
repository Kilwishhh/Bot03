"""Run one local paper-trading cycle without credentials or network access."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from app.database import TradingRepository
from app.exchange.models import Candle
from app.exchange.paper import PaperTradingAdapter
from app.execution import OrderManager
from app.risk import PositionSizer, RiskManager
from app.strategy import IndicatorStrategy


def build_demo_candles() -> list[Candle]:
    start = datetime.now(timezone.utc)
    prices = [100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110]
    return [Candle(
        start + timedelta(minutes=index), Decimal(price), Decimal(price), Decimal(price), Decimal(price), Decimal("1"),
        start + timedelta(minutes=index + 1),
    ) for index, price in enumerate(prices)]


def main() -> None:
    symbol = "BTCUSDT"
    exchange = PaperTradingAdapter(Decimal("1000"))
    strategy = IndicatorStrategy(ema_fast=3, ema_slow=5, rsi_period=3, bb_period=5, adx_period=3)
    signal = strategy.generate_signal(symbol, build_demo_candles())
    repository = TradingRepository("paper_demo.sqlite3")
    repository.save_signal(signal)
    manager = OrderManager(
        exchange,
        RiskManager(Decimal("30"), 3, Decimal("0.7"), 5),
        PositionSizer(Decimal("0.01")),
    )
    result = manager.process_signal(signal)
    if result is not None:
        repository.save_order(result)
    print(f"signal={signal.side.value} confidence={signal.confidence:.2f}")
    print(f"order_status={result.status if result else 'NOT_SUBMITTED'}")
    print(f"saved_signals={repository.count('signals')} saved_orders={repository.count('orders')}")
    repository.close()


if __name__ == "__main__":
    main()