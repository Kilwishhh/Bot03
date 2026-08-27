from .adapter_provider import AdapterMarketDataProvider
from .base import MarketDataProvider
from .candle_store import CandleStore
from .health import MarketDataHealth

__all__ = ["AdapterMarketDataProvider", "CandleStore", "FuturesSignalScanner", "MarketDataHealth", "MarketDataProvider"]


def __getattr__(name: str):
    if name == "FuturesSignalScanner":
        from .scanner import FuturesSignalScanner
        return FuturesSignalScanner
    raise AttributeError(name)
