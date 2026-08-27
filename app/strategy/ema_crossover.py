"""EMA crossover strategy: BUY when fast EMA crosses above slow EMA, SELL on the inverse.

A simple trend-following strategy that reacts to changes in momentum.
Confidence is scaled by the size of the EMA gap relative to price.
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.exchange.models import Candle
from app.signals.models import Signal, SignalSide

from .base import Strategy
from .indicators import ema


class EMACrossoverStrategy(Strategy):
    name = "ema_crossover"

    def __init__(self, ema_fast: int = 9, ema_slow: int = 21) -> None:
        if ema_fast <= 1 or ema_slow <= 1 or ema_fast >= ema_slow:
            raise ValueError("ema_fast must be < ema_slow and both > 1")
        self.ema_fast = ema_fast
        self.ema_slow = ema_slow

    def generate_signal(self, symbol: str, candles: list[Candle]) -> Signal:
        timestamp = candles[-1].close_time if candles else datetime.now(UTC)
        base = {
            "symbol": symbol,
            "timestamp": timestamp,
            "strategy_name": self.__class__.__name__,
        }
        if len(candles) < self.ema_slow + 1:
            return Signal(**base, side=SignalSide.HOLD, confidence=0.0, reason=["insufficient candles"])

        closes = [c.close for c in candles]
        fast_now = ema(closes, self.ema_fast)
        slow_now = ema(closes, self.ema_slow)
        fast_prev = ema(closes[:-1], self.ema_fast)
        slow_prev = ema(closes[:-1], self.ema_slow)

        crossed_up = fast_prev <= slow_prev and fast_now > slow_now
        crossed_down = fast_prev >= slow_prev and fast_now < slow_now

        if crossed_up:
            confidence = min(0.95, 0.7 + float((fast_now - slow_now) / closes[-1]) * 20)
            return Signal(
                **base,
                side=SignalSide.BUY,
                confidence=confidence,
                reason=[f"fast EMA({self.ema_fast}) crossed above slow EMA({self.ema_slow})"],
                metadata={"ema_fast": str(fast_now), "ema_slow": str(slow_now)},
            )
        if crossed_down:
            confidence = min(0.95, 0.7 + float((slow_now - fast_now) / closes[-1]) * 20)
            return Signal(
                **base,
                side=SignalSide.SELL,
                confidence=confidence,
                reason=[f"fast EMA({self.ema_fast}) crossed below slow EMA({self.ema_slow})"],
                metadata={"ema_fast": str(fast_now), "ema_slow": str(slow_now)},
            )
        if fast_now > slow_now:
            return Signal(**base, side=SignalSide.HOLD, confidence=0.0, reason=["fast EMA above slow, no fresh cross"], metadata={"ema_fast": str(fast_now), "ema_slow": str(slow_now)})
        return Signal(**base, side=SignalSide.HOLD, confidence=0.0, reason=["fast EMA below slow, no fresh cross"], metadata={"ema_fast": str(fast_now), "ema_slow": str(slow_now)})
