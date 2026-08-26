"""Small configurable EMA/RSI demonstration strategy."""

from datetime import datetime, timezone
from decimal import Decimal
from app.exchange.models import Candle
from app.signals.models import Signal, SignalSide
from .base import Strategy


class IndicatorStrategy(Strategy):
    def __init__(self, ema_fast: int = 5, ema_slow: int = 10, rsi_period: int = 14, bb_period: int = 20, adx_period: int = 14) -> None:
        if not 1 < ema_fast < ema_slow or rsi_period < 2:
            raise ValueError("indicator periods are invalid")
        self.ema_fast = ema_fast
        self.ema_slow = ema_slow
        self.rsi_period = rsi_period
        self.bb_period = bb_period
        self.adx_period = adx_period

    def generate_signal(self, symbol: str, candles: list[Candle]) -> Signal:
        timestamp = candles[-1].close_time if candles else datetime.now(timezone.utc)
        base = {"symbol": symbol, "timestamp": timestamp, "strategy_name": self.__class__.__name__}
        if len(candles) < max(self.ema_slow, self.rsi_period + 1, self.bb_period, self.adx_period + 1):
            return Signal(**base, side=SignalSide.HOLD, confidence=0.0, reason=["insufficient candles"])
        closes = [c.close for c in candles]
        fast = self._ema(closes, self.ema_fast)
        slow = self._ema(closes, self.ema_slow)
        rsi = self._rsi(closes, self.rsi_period)
        macd = fast - slow
        middle, upper, lower = self._bollinger(closes, self.bb_period)
        adx = self._adx(candles, self.adx_period)
        if fast > slow and rsi >= Decimal("50") and macd >= 0 and closes[-1] >= middle and adx >= Decimal("20"):
            side, reason = SignalSide.BUY, ["EMA bullish", "RSI at or above 50", "MACD positive", "price above Bollinger midline", "ADX confirms trend"]
        elif fast < slow and rsi < Decimal("50") and macd <= 0 and closes[-1] <= middle and adx >= Decimal("20"):
            side, reason = SignalSide.SELL, ["EMA bearish", "RSI below 50", "MACD negative", "price below Bollinger midline", "ADX confirms trend"]
        else:
            side, reason = SignalSide.HOLD, ["indicators do not agree"]
        confidence = min(0.99, 0.7 + float(abs(macd) / closes[-1]) * 10) if side is not SignalSide.HOLD else 0.0
        return Signal(**base, side=side, confidence=confidence, reason=reason, metadata={"ema_fast": str(fast), "ema_slow": str(slow), "rsi": str(rsi), "macd": str(macd), "bb_middle": str(middle), "bb_upper": str(upper), "bb_lower": str(lower), "adx": str(adx)})

    @staticmethod
    def _ema(values: list[Decimal], period: int) -> Decimal:
        multiplier = Decimal("2") / Decimal(period + 1)
        result = values[0]
        for value in values[1:]:
            result = (value - result) * multiplier + result
        return result

    @staticmethod
    def _rsi(values: list[Decimal], period: int) -> Decimal:
        changes = [values[index] - values[index - 1] for index in range(1, len(values))]
        window = changes[-period:]
        gains = sum((change for change in window if change > 0), Decimal("0"))
        losses = sum((-change for change in window if change < 0), Decimal("0"))
        if losses == 0:
            return Decimal("100")
        return Decimal("100") - (Decimal("100") / (Decimal("1") + gains / losses))

    @staticmethod
    def _bollinger(values: list[Decimal], period: int) -> tuple[Decimal, Decimal, Decimal]:
        window = values[-period:]
        middle = sum(window, Decimal("0")) / Decimal(period)
        deviation = (sum((value - middle) ** 2 for value in window) / Decimal(period)).sqrt()
        return middle, middle + Decimal("2") * deviation, middle - Decimal("2") * deviation

    @staticmethod
    def _adx(candles: list[Candle], period: int) -> Decimal:
        moves = [abs(candles[index].close - candles[index - 1].close) for index in range(1, len(candles))]
        ranges = [max(candle.high - candle.low, Decimal("0.00000001")) for candle in candles[-period:]]
        movement = sum(moves[-period:], Decimal("0"))
        average_range = sum(ranges, Decimal("0"))
        return Decimal("100") * movement / average_range if average_range else Decimal("0")