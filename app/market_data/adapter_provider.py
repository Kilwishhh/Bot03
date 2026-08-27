"""Market-data provider backed by any exchange adapter."""

from app.exchange.base import ExchangeAdapter
from app.exchange.models import Candle, Ticker

from .base import MarketDataProvider


class AdapterMarketDataProvider(MarketDataProvider):
    def __init__(self, exchange: ExchangeAdapter) -> None:
        self._exchange = exchange

    def candles(self, symbol: str, timeframe: str, limit: int = 200) -> list[Candle]:
        return self._exchange.get_candles(symbol, timeframe, limit)

    def ticker(self, symbol: str) -> Ticker:
        return self._exchange.get_ticker(symbol)
