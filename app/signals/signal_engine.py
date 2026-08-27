"""Guarded signal generation pipeline."""

from datetime import UTC

from app.exchange.models import Candle
from app.market_data import MarketDataHealth
from app.strategy.base import Strategy

from .models import Signal, SignalSide


class SignalEngine:
    def __init__(self, strategy: Strategy, data_health: MarketDataHealth | None = None) -> None:
        self._strategy = strategy
        self._data_health = data_health or MarketDataHealth()

    def generate(self, symbol: str, candles: list[Candle]) -> Signal:
        if not self._data_health.has_valid_sequence(candles):
            return self._hold(symbol, "market data sequence is invalid")
        if not self._data_health.is_fresh(candles):
            return self._hold(symbol, "market data is stale")
        return self._strategy.generate_signal(symbol, candles)

    @staticmethod
    def _hold(symbol: str, reason: str) -> Signal:
        from datetime import datetime
        return Signal(symbol, SignalSide.HOLD, 0.0, datetime.now(UTC), [reason], "SignalEngine")
