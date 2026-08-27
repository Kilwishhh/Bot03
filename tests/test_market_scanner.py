from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.exchange.models import Candle
from app.exchange.paper import PaperTradingAdapter
from app.market_data import AdapterMarketDataProvider, FuturesSignalScanner
from app.signals import SignalEngine
from app.strategy import IndicatorStrategy


class ScanPaperAdapter(PaperTradingAdapter):
    def get_symbols(self):
        return ["BTCUSDT", "ETHUSDT"]

    def get_candles(self, symbol, interval, limit=200):
        now = datetime.now(UTC)
        return [Candle(now - timedelta(minutes=10 - i), Decimal(100 + i), Decimal(100 + i), Decimal(100 + i), Decimal(100 + i), Decimal("1"), now - timedelta(minutes=9 - i)) for i in range(11)]


def test_scanner_discovers_and_scans_all_symbols():
    exchange = ScanPaperAdapter()
    scanner = FuturesSignalScanner(exchange, AdapterMarketDataProvider(exchange), SignalEngine(IndicatorStrategy(3, 5, 3, 5, 3)))
    signals = scanner.scan("15m")
    assert [signal.symbol for signal in signals] == ["BTCUSDT", "ETHUSDT"]
    assert all(signal.side.value == "BUY" for signal in signals)
