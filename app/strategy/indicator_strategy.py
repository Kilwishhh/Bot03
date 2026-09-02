"""EMA/RSI/MACD/Bollinger/ADX ensemble strategy — the original default."""

from datetime import UTC, datetime
from decimal import Decimal

from app.exchange.models import Candle
from app.signals.models import Signal, SignalSide

from .base import Strategy
from .indicators import adx, bollinger, ema, rsi


class IndicatorStrategy(Strategy):
    """Ensemble of five indicators: EMA crossover + RSI + MACD + Bollinger + ADX.

    BUY  when EMA fast > slow, RSI >= 50, MACD >= 0, price above BB middle,
          and ADX confirms a trend.
    SELL when EMA fast < slow, RSI < 50, MACD < 0, price below BB middle,
          and ADX confirms a trend.
    HOLD otherwise.
    """

    name = "indicator"

    def __init__(
        self,
        ema_fast: int = 20,
        ema_slow: int = 50,
        rsi_period: int = 14,
        bb_period: int = 20,
        adx_period: int = 14,
    ) -> None:
        if not 1 < ema_fast < ema_slow or rsi_period < 2:
            raise ValueError("indicator periods are invalid")
        self.ema_fast = ema_fast
        self.ema_slow = ema_slow
        self.rsi_period = rsi_period
        self.bb_period = bb_period
        self.adx_period = adx_period

    def generate_signal(self, symbol: str, candles: list[Candle]) -> Signal:
        timestamp = candles[-1].close_time if candles else datetime.now(UTC)
        base = {
            "symbol": symbol,
            "timestamp": timestamp,
            "strategy_name": self.__class__.__name__,
        }
        if len(candles) < max(self.ema_slow, self.rsi_period + 1, self.bb_period, self.adx_period + 1):
            return Signal(**base, side=SignalSide.HOLD, confidence=0.0, reason=["insufficient candles"])

        closes = [float(c.close) for c in candles]
        fast_ema = ema(closes, self.ema_fast)
        slow_ema = ema(closes, self.ema_slow)
        rsi_val = rsi(closes, self.rsi_period)
        macd = (fast_ema - slow_ema) if (fast_ema is not None and slow_ema is not None) else None
        upper_middle_lower = bollinger(closes, self.bb_period)
        middle = upper_middle_lower[1] if upper_middle_lower is not None else None
        adx_val = adx(candles, self.adx_period)

        if (
            fast_ema is not None
            and slow_ema is not None
            and rsi_val is not None
            and macd is not None
            and middle is not None
            and adx_val is not None
            and fast_ema > slow_ema
            and rsi_val >= 50
            and macd >= 0
            and closes[-1] >= middle
            and adx_val >= 20
        ):
            side, reason = SignalSide.BUY, [
                "EMA bullish",
                f"RSI={rsi_val:.1f} at or above 50",
                f"MACD={macd} positive",
                "price above Bollinger midline",
                f"ADX={adx_val:.1f} confirms trend",
            ]
        elif (
            fast_ema is not None
            and slow_ema is not None
            and rsi_val is not None
            and macd is not None
            and middle is not None
            and adx_val is not None
            and fast_ema < slow_ema
            and rsi_val < 50
            and macd <= 0
            and closes[-1] <= middle
            and adx_val >= 20
        ):
            side, reason = SignalSide.SELL, [
                "EMA bearish",
                f"RSI={rsi_val:.1f} below 50",
                f"MACD={macd} negative",
                "price below Bollinger midline",
                f"ADX={adx_val:.1f} confirms trend",
            ]
        else:
            side, reason = SignalSide.HOLD, ["indicators do not agree"]

        confidence = (
            min(0.99, 0.7 + float(abs(macd) / closes[-1]) * 10)
            if (side is not SignalSide.HOLD and macd is not None)
            else 0.0
        )
        upper_v = upper_middle_lower[0] if upper_middle_lower is not None else None
        lower_v = upper_middle_lower[2] if upper_middle_lower is not None else None
        return Signal(
            **base,
            side=side,
            confidence=confidence,
            reason=reason,
            metadata={
                "ema_fast": str(fast_ema),
                "ema_slow": str(slow_ema),
                "rsi": str(rsi_val),
                "macd": str(macd),
                "bb_middle": str(middle),
                "bb_upper": str(upper_v),
                "bb_lower": str(lower_v),
                "adx": str(adx_val),
            },
        )
