from decimal import Decimal
from datetime import datetime, timedelta, timezone
from app.database import TradingRepository
from app.exchange.models import Candle
from app.exchange.paper import PaperTradingAdapter
from app.execution import OrderManager
from app.market_data import AdapterMarketDataProvider
from app.risk import PositionSizer, RiskManager
from app.runtime import TradingCycle
from app.signals import SignalEngine
from app.strategy import IndicatorStrategy


class DemoPaperAdapter(PaperTradingAdapter):
    def get_candles(self, symbol, interval, limit=200):
        now = datetime.now(timezone.utc)
        return [Candle(now - timedelta(minutes=10 - i), Decimal(100 + i), Decimal(100 + i), Decimal(100 + i), Decimal(100 + i), Decimal("1"), now - timedelta(minutes=9 - i)) for i in range(11)]


def test_trading_cycle_persists_signal_and_order(tmp_path):
    exchange = DemoPaperAdapter(Decimal("1000"))
    repository = TradingRepository(tmp_path / "cycle.sqlite3")
    cycle = TradingCycle(
        AdapterMarketDataProvider(exchange),
        SignalEngine(IndicatorStrategy(3, 5, 3, 5, 3)),
        OrderManager(exchange, RiskManager(Decimal("30"), 3, Decimal("0.7"), 5), PositionSizer(Decimal("0.01"))),
        repository,
    )
    signal, result = cycle.run_once("BTCUSDT", "15m")
    assert signal.side.value == "BUY"
    assert result is not None
    assert repository.count("signals") == 1
    assert repository.count("orders") == 1
    assert repository.count("bot_events") == 1
    repository.close()