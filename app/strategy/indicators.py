"""Reusable technical-indicator helpers used by every built-in strategy.

Centralising the math keeps each strategy focused on its decision logic
and ensures the same number comes out the same way no matter which
strategy computed it.
"""

from __future__ import annotations

from decimal import Decimal


def sma(values: list[Decimal], period: int) -> Decimal:
    """Simple moving average over the trailing ``period`` values."""
    if period <= 0 or len(values) < period:
        raise ValueError("not enough values for the requested period")
    window = values[-period:]
    return sum(window, Decimal("0")) / Decimal(period)


def ema(values: list[Decimal], period: int) -> Decimal:
    """Exponential moving average seeded with the first value."""
    if period <= 0 or not values:
        raise ValueError("period must be positive and values must not be empty")
    multiplier = Decimal("2") / Decimal(period + 1)
    result = values[0]
    for value in values[1:]:
        result = (value - result) * multiplier + result
    return result


def rsi(values: list[Decimal], period: int = 14) -> Decimal:
    """Relative Strength Index over the trailing ``period`` changes."""
    if period <= 0 or len(values) < period + 1:
        raise ValueError("not enough values for the requested period")
    changes = [values[i] - values[i - 1] for i in range(1, len(values))]
    window = changes[-period:]
    gains = sum((c for c in window if c > 0), Decimal("0"))
    losses = sum((-c for c in window if c < 0), Decimal("0"))
    if losses == 0:
        return Decimal("100")
    return Decimal("100") - (Decimal("100") / (Decimal("1") + gains / losses))


def macd(values: list[Decimal], fast: int = 12, slow: int = 26, signal: int = 9) -> tuple[Decimal, Decimal, Decimal]:
    """MACD line, signal line, and histogram from EMA(fast) − EMA(slow)."""
    if fast <= 0 or slow <= 0 or signal <= 0:
        raise ValueError("macd periods must be positive")
    if fast >= slow:
        raise ValueError("fast period must be smaller than slow period")
    if len(values) < slow + signal:
        raise ValueError("not enough values for macd")
    # MACD is the diff of two EMAs. We compute a single EMA series for
    # both the fast and slow windows, then take the trailing series of
    # differences to derive a signal EMA.
    fast_series: list[Decimal] = []
    slow_series: list[Decimal] = []
    for i in range(len(values)):
        if i + 1 < fast:
            continue
        fast_series.append(ema(values[: i + 1], fast))
    for i in range(len(values)):
        if i + 1 < slow:
            continue
        slow_series.append(ema(values[: i + 1], slow))
    # align the two series by trimming the longer one from the left
    offset = len(slow_series) - len(fast_series)
    aligned_slow = slow_series[offset:] if offset > 0 else slow_series
    offset = len(fast_series) - len(slow_series)
    aligned_fast = fast_series[offset:] if offset > 0 else fast_series
    diff_series = [f - s for f, s in zip(aligned_fast, aligned_slow, strict=False)]
    macd_line = diff_series[-1]
    signal_line = ema(diff_series, signal) if len(diff_series) >= signal else diff_series[-1]
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def bollinger(values: list[Decimal], period: int = 20, std_multiplier: Decimal = Decimal("2")) -> tuple[Decimal, Decimal, Decimal]:
    """Bollinger Bands: middle, upper, lower."""
    if period <= 0 or len(values) < period:
        raise ValueError("not enough values for the requested period")
    window = values[-period:]
    middle = sum(window, Decimal("0")) / Decimal(period)
    variance = sum((v - middle) ** 2 for v in window) / Decimal(period)
    std = variance.sqrt()
    return middle, middle + std_multiplier * std, middle - std_multiplier * std


def true_range(high: Decimal, low: Decimal, prev_close: Decimal) -> Decimal:
    """True range for a single candle."""
    return max(high - low, abs(high - prev_close), abs(low - prev_close))


def atr(highs: list[Decimal], lows: list[Decimal], closes: list[Decimal], period: int = 14) -> Decimal:
    """Average True Range over the trailing ``period`` candles."""
    if period <= 0 or len(closes) < period + 1:
        raise ValueError("not enough values for the requested period")
    trs: list[Decimal] = []
    for i in range(1, len(closes)):
        if i - 1 < period - 1:
            continue
        # accumulate trailing `period` true ranges
        start = max(1, i - period + 1)
        seg = [
            true_range(highs[j], lows[j], closes[j - 1])
            for j in range(start, i + 1)
            if highs[j] is not None and lows[j] is not None and closes[j - 1] is not None
        ]
        if seg:
            trs.append(sum(seg, Decimal("0")) / Decimal(len(seg)))
    if not trs:
        raise ValueError("not enough values for atr")
    return trs[-1]


def adx(candles: list, period: int = 14) -> Decimal:
    """Simplified Average Directional Index using average directional movement.

    This implementation tracks the magnitude of net movement relative to
    the average true range; it's adequate for an ADX-style trend-strength
    filter that the ensemble strategy uses, not for full Wilder ADX.
    """
    if period <= 0 or len(candles) < period + 1:
        raise ValueError("not enough candles for adx")
    moves = [abs(candles[i].close - candles[i - 1].close) for i in range(1, len(candles))]
    ranges = [max(candle.high - candle.low, Decimal("0.00000001")) for candle in candles[-period:]]
    movement = sum(moves[-period:], Decimal("0"))
    average_range = sum(ranges, Decimal("0"))
    return Decimal("100") * movement / average_range if average_range else Decimal("0")


def stddev(values: list[Decimal]) -> Decimal:
    """Sample standard deviation of a list of values."""
    if len(values) < 2:
        return Decimal("0")
    mean = sum(values, Decimal("0")) / Decimal(len(values))
    variance = sum((v - mean) ** 2 for v in values) / Decimal(len(values) - 1)
    return variance.sqrt()
