"""MACD crossover strategy: BUY when MACD line crosses above its signal line, SELL on the inverse."""

from __future__ import annotations

from datetime import UTC, datetime

from app.exchange.models import Candle
from app.signals.models import Signal, SignalSide

from .base import Strategy
from .indicators import macd


class MACDCrossoverStrategy(Strategy):
    name = "macd_crossover"

    def __init__(self, fast: int = 12, slow: int = 26, signal_period: int = 9) -> None:
        if fast <= 0 or slow <= 0 or signal_period <= 0:
            raise ValueError("macd periods must be positive")
        if fast >= slow:
            raise ValueError("fast must be smaller than slow")
        self.fast = fast
        self.slow = slow
        self.signal_period = signal_period

    def generate_signal(self, symbol: str, candles: list[Candle]) -> Signal:
        timestamp = candles[-1].close_time if candles else datetime.now(UTC)
        base = {
            "symbol": symbol,
            "timestamp": timestamp,
            "strategy_name": self.__class__.__name__,
        }
        if len(candles) < self.slow + self.signal_period + 1:
            return Signal(**base, side=SignalSide.HOLD, confidence=0.0, reason=["insufficient candles"])

        closes = [c.close for c in candles]
        macd_line, signal_line, _ = macd(closes, self.fast, self.slow, self.signal_period)
        macd_prev, signal_prev, _ = macd(closes[:-1], self.fast, self.slow, self.signal_period)

        crossed_up = macd_prev <= signal_prev and macd_line > signal_line
        crossed_down = macd_prev >= signal_prev and macd_line < signal_line

        if crossed_up:
            confidence = min(0.95, 0.7 + float((macd_line - signal_line) / closes[-1]) * 50)
            return Signal(
                **base,
                side=SignalSide.BUY,
                confidence=confidence,
                reason=[f"MACD line crossed above signal line ({self.fast}/{self.slow}/{self.signal_period})"],
                metadata={"macd": str(macd_line), "signal": str(signal_line)},
            )
        if crossed_down:
            confidence = min(0.95, 0.7 + float((signal_line - macd_line) / closes[-1]) * 50)
            return Signal(
                **base,
                side=SignalSide.SELL,
                confidence=confidence,
                reason=[f"MACD line crossed below signal line ({self.fast}/{self.slow}/{self.signal_period})"],
                metadata={"macd": str(macd_line), "signal": str(signal_line)},
            )
        return Signal(
            **base,
            side=SignalSide.HOLD,
            confidence=0.0,
            reason=["no MACD cross"],
            metadata={"macd": str(macd_line), "signal": str(signal_line)},
        )
