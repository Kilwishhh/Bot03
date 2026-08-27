# Example user-defined strategy — the simplest possible custom strategy.

# To enable: set `STRATEGY=my_first_strategy` in your .env (or remove the
# leading underscore from this file's name once you have adapted it).

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from app.exchange.models import Candle
from app.signals.models import Signal, SignalSide
from app.strategy.base import Strategy


class _MyFirstStrategy(Strategy):
    """A simple momentum strategy: BUY if last close > SMA(20), SELL otherwise."""

    name = "my_first_strategy"

    def __init__(self, period: int = 20) -> None:
        self.period = period

    def generate_signal(self, symbol: str, candles: list[Candle]) -> Signal:
        timestamp = candles[-1].close_time if candles else datetime.now(UTC)
        base = {"symbol": symbol, "timestamp": timestamp, "strategy_name": self.__class__.__name__}
        if len(candles) < self.period:
            return Signal(**base, side=SignalSide.HOLD, confidence=0.0, reason=["insufficient candles"])
        closes = [c.close for c in candles]
        mean = sum(closes[-self.period:], Decimal("0")) / Decimal(self.period)
        last = closes[-1]
        if last > mean:
            return Signal(**base, side=SignalSide.BUY, confidence=0.75, reason=[f"close {last} above SMA({self.period}) {mean}"])
        return Signal(**base, side=SignalSide.SELL, confidence=0.75, reason=[f"close {last} below SMA({self.period}) {mean}"])


def build(_settings):
    return _MyFirstStrategy()
