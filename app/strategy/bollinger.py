"""Bollinger band breakout / reversion strategy.

Two modes:
  * breakout (default) — BUY when price closes above the upper band,
    SELL when it closes below the lower band. Trend-following.
  * reversion — BUY when price closes below the lower band (oversold),
    SELL when it closes above the upper band (overbought). Mean-reverting.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from app.exchange.models import Candle
from app.signals.models import Signal, SignalSide

from .base import Strategy
from .indicators import bollinger


class BollingerStrategy(Strategy):
    name = "bollinger"

    def __init__(self, period: int = 20, std_multiplier: Decimal = Decimal("2"), mode: str = "breakout") -> None:
        if period <= 1:
            raise ValueError("period must be > 1")
        if std_multiplier <= 0:
            raise ValueError("std_multiplier must be positive")
        if mode not in {"breakout", "reversion"}:
            raise ValueError("mode must be 'breakout' or 'reversion'")
        self.period = period
        self.std_multiplier = std_multiplier
        self.mode = mode

    def generate_signal(self, symbol: str, candles: list[Candle]) -> Signal:
        timestamp = candles[-1].close_time if candles else datetime.now(UTC)
        base = {
            "symbol": symbol,
            "timestamp": timestamp,
            "strategy_name": self.__class__.__name__,
        }
        if len(candles) < self.period:
            return Signal(**base, side=SignalSide.HOLD, confidence=0.0, reason=["insufficient candles"])

        closes = [c.close for c in candles]
        middle, upper, lower = bollinger(closes, self.period, self.std_multiplier)
        last = closes[-1]

        if self.mode == "breakout":
            if last > upper:
                confidence = min(0.95, 0.7 + float((last - upper) / upper) * 10)
                return Signal(
                    **base,
                    side=SignalSide.BUY,
                    confidence=confidence,
                    reason=[f"close {last} above upper Bollinger band {upper}"],
                    metadata={"upper": str(upper), "lower": str(lower), "middle": str(middle)},
                )
            if last < lower:
                confidence = min(0.95, 0.7 + float((lower - last) / lower) * 10)
                return Signal(
                    **base,
                    side=SignalSide.SELL,
                    confidence=confidence,
                    reason=[f"close {last} below lower Bollinger band {lower}"],
                    metadata={"upper": str(upper), "lower": str(lower), "middle": str(middle)},
                )
        else:  # reversion
            if last < lower:
                confidence = min(0.95, 0.7 + float((lower - last) / lower) * 10)
                return Signal(
                    **base,
                    side=SignalSide.BUY,
                    confidence=confidence,
                    reason=[f"close {last} below lower band {lower} (oversold)"],
                    metadata={"upper": str(upper), "lower": str(lower), "middle": str(middle)},
                )
            if last > upper:
                confidence = min(0.95, 0.7 + float((last - upper) / upper) * 10)
                return Signal(
                    **base,
                    side=SignalSide.SELL,
                    confidence=confidence,
                    reason=[f"close {last} above upper band {upper} (overbought)"],
                    metadata={"upper": str(upper), "lower": str(lower), "middle": str(middle)},
                )
        return Signal(
            **base,
            side=SignalSide.HOLD,
            confidence=0.0,
            reason=["price within Bollinger bands"],
            metadata={"upper": str(upper), "lower": str(lower), "middle": str(middle)},
        )
