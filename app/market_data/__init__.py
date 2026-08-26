from .health import MarketDataHealth
from .adapter_provider import AdapterMarketDataProvider
from .base import MarketDataProvider
from .candle_store import CandleStore

__all__ = ["AdapterMarketDataProvider", "CandleStore", "FuturesSignalScanner", "MarketDataHealth", "MarketDataProvider"]


def __getattr__(name: str):
	if name == "FuturesSignalScanner":
		from .scanner import FuturesSignalScanner
		return FuturesSignalScanner
	raise AttributeError(name)