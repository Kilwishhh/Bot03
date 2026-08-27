"""Market-data provider contract."""

from abc import ABC, abstractmethod

from app.exchange.models import Candle, Ticker


class MarketDataProvider(ABC):
    @abstractmethod
    def candles(self, symbol: str, timeframe: str, limit: int = 200) -> list[Candle]: ...

    @abstractmethod
    def ticker(self, symbol: str) -> Ticker: ...
