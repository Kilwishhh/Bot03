"""RSI mean-reversion strategy.

BUY when RSI is below the oversold threshold, SELL when RSI is above the
overbought threshold. Confidence scales with how far RSI is from the
midline (50).
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from app.exchange.models import Candle
from app.signals.models import Signal, SignalSide

from .base import Strategy
from .indicators import rsi


class RSIMeanReversionStrategy(Strategy):
    name = "rsi_mean_reversion"

    def __init__(self, period: int = 14, oversold: Decimal = Decimal("30"), overbought: Decimal = Decimal("70")) -> None:
        if period <= 1:
            raise ValueError("period must be > 1")
        if not (Decimal("0") < oversold < Decimal("50")):
            raise ValueError("oversold must be between 0 and 50")
        if not (Decimal("50") < overbought < Decimal("100")):
            raise ValueError("overbought must be between 50 and 100")
        self.period = period
        self.oversold = oversold
        self.overbought = overbought

    def generate_signal(self, symbol: str, candles: list[Candle]) -> Signal:
        timestamp = candles[-1].close_time if candles else datetime.now(UTC)
        base = {
            "symbol": symbol,
            "timestamp": timestamp,
            "strategy_name": self.__class__.__name__,
        }
        if len(candles) < self.period + 1:
            return Signal(**base, side=SignalSide.HOLD, confidence=0.0, reason=["insufficient candles"])

        closes = [float(c.close) for c in candles]
        value = rsi(closes, self.period)

        if value < self.oversold:
            confidence = min(0.95, 0.7 + float((float(self.oversold) - value) / 100))
            return Signal(
                **base,
                side=SignalSide.BUY,
                confidence=confidence,
                reason=[f"RSI({self.period})={value} below oversold {self.oversold}"],
                metadata={"rsi": str(value)},
            )
        if value > self.overbought:
            confidence = min(0.95, 0.7 + float((value - float(self.overbought)) / 100))
            return Signal(
                **base,
                side=SignalSide.SELL,
                confidence=confidence,
                reason=[f"RSI({self.period})={value} above overbought {self.overbought}"],
                metadata={"rsi": str(value)},
            )
        return Signal(**base, side=SignalSide.HOLD, confidence=0.0, reason=[f"RSI({self.period})={value} in neutral band"], metadata={"rsi": str(value)})
