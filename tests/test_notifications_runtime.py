from decimal import Decimal

from app.database import TradingRepository
from app.exchange.paper import PaperTradingAdapter
from app.execution import OrderManager
from app.market_data import AdapterMarketDataProvider
from app.notifications import SignalPublisher
from app.risk import PositionSizer, RiskManager
from app.runtime import TradingCycle
from app.signals import SignalEngine
from app.strategy import IndicatorStrategy


class RecordingPublisher(SignalPublisher):
    def __init__(self):
        self.signals = []

    def publish(self, signal):
        self.signals.append(signal)


class EmptyPublisher(SignalPublisher):
    def publish(self, signal):
        raise RuntimeError("notification unavailable")


def test_notification_failure_does_not_stop_cycle(tmp_path):
    exchange = PaperTradingAdapter(Decimal("1000"))
    repository = TradingRepository(tmp_path / "notifications.sqlite3")
    cycle = TradingCycle(AdapterMarketDataProvider(exchange), SignalEngine(IndicatorStrategy()), OrderManager(exchange, RiskManager(Decimal("30"), 3, Decimal("0.7"), 5), PositionSizer(Decimal("0.01"))), repository, EmptyPublisher())
    signal, _ = cycle.run_once("BTCUSDT", "15m")
    assert signal.side.value == "HOLD"
    assert repository.count("signals") == 1
    assert repository.count("errors") == 1
    repository.close()
