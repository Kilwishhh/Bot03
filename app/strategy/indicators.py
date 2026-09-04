"""Indicator computation engine.

Each function takes a list of closing prices (oldest first) and returns
the current indicator value as a float.  Functions that need open/high/low
receive the full Candle object list instead.
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.exchange.models import Candle


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _prices(candles: list["Candle"]) -> list[float]:
    """Accept candle objects OR raw numeric values. Always returns floats.

    Checks Decimal before checking for candle.close attribute because Decimal
    objects have a .close() method that would incorrectly be treated as
    candle data.
    """
    if not candles:
        return []
    first = candles[0]
    # Check Decimal before "hasattr close" — Decimal.close is a rounding method
    from decimal import Decimal
    if isinstance(first, Decimal):
        return [float(v) for v in candles]
    # Raw numeric list
    if isinstance(first, (float, int)):
        return [float(v) for v in candles]
    # Real candle object
    if hasattr(first, "close"):
        return [float(c.close) for c in candles]
    return [float(v) for v in candles]


def ema(candles: list["Candle"], period: int = 21) -> float | None:
    """Legacy alias — same as ema_custom."""
    return ema_custom(candles, period)


def adx(candles: list["Candle"], period: int = 14) -> float | None:
    """Simplified ADX approximation: returns 0 if insufficient data.

    Real ADX needs the full +DI/-DI pipeline. This stub keeps the
    import surface compatible with existing strategy files.
    """
    if len(candles) < period * 2:
        return None
    return 25.0  # neutral placeholder; not used in real signals


def bollinger(candles: list["Candle"],
              period: int = 20,
              std_multiplier: float = 2.0
              ) -> tuple[float | None, float | None, float | None] | None:
    """Legacy alias for bollinger_bands."""
    return bollinger_bands(candles, period, float(std_multiplier))


def _ohlc(candles: list["Candle"]) -> tuple[list[float], list[float], list[float], list[float]]:
    if not candles:
        return [], [], [], []
    first = candles[0]
    # Raw numeric list
    if isinstance(first, (float, int)):
        closes = [float(v) for v in candles]
        return closes, closes, closes, closes
    opens  = [float(c.open)  for c in candles]
    highs  = [float(c.high)  for c in candles]
    lows   = [float(c.low)   for c in candles]
    closes = [float(c.close) for c in candles]
    return opens, highs, lows, closes


def _ema(values, period: int):
    """Exponential moving average — returns latest value or None if insufficient data."""
    if len(values) < period:
        return None
    k = 2.0 / (period + 1)
    ema_val = sum(values[:period]) / period
    for v in values[period:]:
        ema_val = v * k + ema_val * (1 - k)
    return ema_val


# ---------------------------------------------------------------------------
# EMA
# ---------------------------------------------------------------------------

def ema_fast(candles: list["Candle"]) -> float | None:
    """Default 9-period fast EMA."""
    return ema_fast_custom(candles, 9)


def ema_fast_custom(candles: list["Candle"], period: int) -> float | None:
    if len(candles) < period:
        return None
    return _ema(_prices(candles), period)


def ema_slow(candles: list["Candle"]) -> float | None:
    """Default 21-period slow EMA."""
    return ema_slow_custom(candles, 21)


def ema_slow_custom(candles: list["Candle"], period: int) -> float | None:
    if len(candles) < period:
        return None
    return _ema(_prices(candles), period)


def ema_custom(candles: list["Candle"], period: int) -> float | None:
    """Generic EMA for any period."""
    if len(candles) < period:
        return None
    return _ema(_prices(candles), period)


# ---------------------------------------------------------------------------
# SMA
# ---------------------------------------------------------------------------

def sma(candles: list["Candle"], period: int) -> float | None:
    if len(candles) < period:
        return None
    vals = _prices(candles)
    return sum(vals[-period:]) / period


# ---------------------------------------------------------------------------
# RSI
# ---------------------------------------------------------------------------

def rsi(candles, period: int = 14):
    if len(candles) < period + 1:
        return None
    closes = _prices(candles)
    gains, losses = [], []
    for i in range(1, len(closes)):
        delta = closes[i] - closes[i - 1]
        gains.append(max(delta, 0.0))
        losses.append(max(-delta, 0.0))
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


# ---------------------------------------------------------------------------
# MACD
# ---------------------------------------------------------------------------

def macd(candles: list["Candle"],
         fast: int = 12, slow: int = 26, signal: int = 9
         ) -> tuple[float | None, float | None, float | None] | None:
    """Returns (macd_line, signal_line, histogram) or None if insufficient data."""
    fast, slow, signal = int(fast), int(slow), int(signal)
    if len(candles) < slow + signal:
        return None
    closes = _prices(candles)
    ema_fast_val = _ema(closes, fast)
    ema_slow_val = _ema(closes, slow)
    if ema_fast_val is None or ema_slow_val is None:
        return None
    macd_line = ema_fast_val - ema_slow_val
    # Build MACD series to compute signal line
    macd_series: list[float] = []
    for i in range(slow - 1, len(closes)):
        ef = _ema(closes[:i + 1], fast) or 0
        es = _ema(closes[:i + 1], slow) or 0
        macd_series.append(ef - es)
    if len(macd_series) < signal:
        return None
    sig = _ema(macd_series, signal)
    hist = macd_line - sig if sig is not None else None
    return macd_line, sig, hist


# ---------------------------------------------------------------------------
# Bollinger Bands
# ---------------------------------------------------------------------------

def bollinger_bands(candles: list["Candle"],
                    period: int = 20,
                    std_multiplier: float = 2.0
                    ) -> tuple[float | None, float | None, float | None] | None:
    """Returns (upper, middle, lower) or None if insufficient data."""
    if len(candles) < period:
        return None
    closes = _prices(candles)
    mid = sma(candles, period)
    if mid is None:
        return None
    std_mult = float(std_multiplier)  # handle Decimal param from legacy callers
    variance = sum((c - mid) ** 2 for c in closes[-period:]) / period
    std = variance ** 0.5
    return mid + std_mult * std, mid, mid - std_mult * std


# ---------------------------------------------------------------------------
# Volume
# ---------------------------------------------------------------------------

def volume_avg(candles: list["Candle"], period: int = 20) -> float | None:
    if len(candles) < period:
        return None
    recent = []
    for c in candles[-period:]:
        if isinstance(c, (float, int)):
            recent.append(float(c))
        else:
            recent.append(float(c.volume))
    return sum(recent) / len(recent)


def volume(candles: list["Candle"]) -> float | None:
    """Current bar volume (or last value if raw list)."""
    if not candles:
        return None
    v = candles[-1]
    if isinstance(v, (float, int)):
        return float(v)
    return float(v.volume)


# ---------------------------------------------------------------------------
# Price
# ---------------------------------------------------------------------------

def price(candles: list["Candle"]) -> float | None:
    """Latest close price (accepts raw numeric list too)."""
    if not candles:
        return None
    v = candles[-1]
    if isinstance(v, (float, int)):
        return float(v)
    return float(v.close)


def high(candles: list["Candle"]) -> float | None:
    if not candles:
        return None
    v = candles[-1]
    if isinstance(v, (float, int)):
        return float(v)
    return float(v.high)


def low(candles: list["Candle"]) -> float | None:
    if not candles:
        return None
    v = candles[-1]
    if isinstance(v, (float, int)):
        return float(v)
    return float(v.low)


def open_price(candles: list["Candle"]) -> float | None:
    if not candles:
        return None
    v = candles[-1]
    if isinstance(v, (float, int)):
        return float(v)
    return float(v.open)


# ---------------------------------------------------------------------------
# Compute all indicators from a config list
# ---------------------------------------------------------------------------

# ------------------------------------------------------------------------------------------------------------------------------------------
# Timeframe helpers
# ------------------------------------------------------------------------------------------------------------------------------------------

def get_timeframe_minutes(tf: str) -> int:
    """Convert a timeframe string (e.g. '7m', '2h', '1d', '1w', '1M') to total minutes.

    Binance uses 'M' (uppercase) for month, distinct from 'm' for minute. We
    preserve the case of the unit suffix. Anything unparseable raises ValueError.
    """
    if not tf:
        raise ValueError("empty timeframe")
    s = tf.strip()
    # Preserve case for the unit suffix
    if s.endswith("M"):
        return int(s[:-1]) * 30 * 1440  # Binance month ≈ 30 days
    s_lower = s.lower()
    if s_lower.endswith("w"):
        return int(s_lower[:-1]) * 7 * 1440
    if s_lower.endswith("d"):
        return int(s_lower[:-1]) * 1440
    if s_lower.endswith("h"):
        return int(s_lower[:-1]) * 60
    if s_lower.endswith("m"):
        return int(s_lower[:-1])
    raise ValueError(f"unsupported timeframe: {tf}")


# ------------------------------------------------------------------------------------------------------------------------------------------
# Indicator computation
# ------------------------------------------------------------------------------------------------------------------------------------------

def compute_indicators(
    candles: list["Candle"],
    config: list[dict],
) -> dict[str, float | None]:
    """Compute all enabled indicators from a config list.

    Each config item: {"type": "RSI", "params": {"period": 14}, "enabled": true}
    Returns: {"RSI": 45.2, "EMA_FAST": 50100.0, ...}
    """
    result: dict[str, float | None] = {}
    for item in config:
        if not item.get("enabled", True):
            continue
        t = str(item.get("type", item.get("name", ""))).upper()
        params = item.get("params", {}) or {}
        if t == "EMA":
            period = int(params.get("period", 21))
            v = ema_custom(candles, period)
            result[f"EMA_{period}"] = float(v) if v is not None else None
        elif t == "RSI":
            period = int(params.get("period", 14))
            v = rsi(candles, period)
            result[f"RSI_{period}"] = float(v) if v is not None else None
        elif t == "MACD":
            f = int(params.get("fast_period", 12))
            s = int(params.get("slow_period", 26))
            sig = int(params.get("signal_period", 9))
            res = macd(candles, f, s, sig)
            if res:
                result["MACD_LINE"] = float(res[0]) if res[0] is not None else None
                result["MACD_SIGNAL"] = float(res[1]) if res[1] is not None else None
                result["MACD_HIST"] = float(res[2]) if res[2] is not None else None
        elif t == "BOLLINGER":
            period = int(params.get("period", 20))
            std = float(params.get("std_multiplier", 2.0))
            res = bollinger_bands(candles, period, std)
            if res:
                result["BB_UPPER"] = float(res[0]) if res[0] is not None else None
                result["BB_MIDDLE"] = float(res[1]) if res[1] is not None else None
                result["BB_LOWER"] = float(res[2]) if res[2] is not None else None
        elif t == "VOLUME":
            v = volume(candles)
            result["VOLUME"] = float(v) if v is not None else None
        elif t == "SMA":
            period = int(params.get("period", 20))
            v = sma(candles, period)
            result[f"SMA_{period}"] = float(v) if v is not None else None
    # Always add price for condition evaluation
    p = price(candles)
    if p is not None:
        result["PRICE"] = float(p)
    elif "PRICE" not in result:
        result["PRICE"] = None
    return result


def compute_indicator_votes(candles: list["Candle"], config: list[dict]) -> list[dict]:
    """Return beginner-friendly LONG/SHORT/NEUTRAL votes for enabled indicators."""
    closes = _prices(candles)
    if not closes:
        return []
    current = closes[-1]
    previous = closes[-2] if len(closes) > 1 else current
    votes: list[dict] = []
    for item in config:
        if not item.get("enabled", True):
            continue
        name = str(item.get("name", item.get("type", ""))).upper()
        params = item.get("params", {}) or {}
        vote = "NEUTRAL"
        detail = ""
        if name == "RSI":
            value = rsi(candles, int(params.get("period", 14)))
            oversold = float(params.get("oversold", 30))
            overbought = float(params.get("overbought", 70))
            if value is not None:
                vote = "LONG" if value <= oversold else "SHORT" if value >= overbought else vote
                detail = f"RSI {value:.1f}"
        elif name == "MACD":
            result = macd(candles, int(params.get("fast_period", 12)), int(params.get("slow_period", 26)), int(params.get("signal_period", 9)))
            if result and result[0] is not None and result[1] is not None:
                vote = "LONG" if result[0] > result[1] else "SHORT" if result[0] < result[1] else vote
                detail = "MACD line vs signal"
        elif name in ("EMA_CROSSOVER", "EMA CROSSOVER"):
            fast = ema_custom(candles, int(params.get("fast_period", 20)))
            slow = ema_custom(candles, int(params.get("slow_period", 50)))
            if fast is not None and slow is not None:
                vote = "LONG" if fast > slow else "SHORT" if fast < slow else vote
                detail = "fast EMA vs slow EMA"
        elif name == "VOLUME":
            period = int(params.get("period", 20))
            volumes = [float(c.volume) for c in candles]
            if len(volumes) >= period + 1:
                average = sum(volumes[-period - 1:-1]) / period
                if volumes[-1] > average:
                    vote = "LONG" if current > previous else "SHORT" if current < previous else vote
                    detail = "volume confirms candle direction"
        elif name in ("BOLLINGER", "BBANDS"):
            result = bollinger_bands(candles, int(params.get("period", 20)), float(params.get("std_multiplier", 2)))
            if result and result[0] is not None and result[2] is not None:
                vote = "LONG" if current <= result[2] else "SHORT" if current >= result[0] else vote
                detail = "price vs bands"
        elif name in ("STOCH", "STOCHASTIC"):
            period = int(params.get("k_period", params.get("period", 14)))
            d_period = int(params.get("d_period", 3))
            if len(candles) >= period + d_period:
                k_values = []
                for end in range(period, len(candles) + 1):
                    window = candles[end - period:end]
                    high = max(float(c.high) for c in window)
                    low = min(float(c.low) for c in window)
                    close = float(window[-1].close)
                    k_values.append(50.0 if high == low else (close - low) / (high - low) * 100)
                k = k_values[-1]
                d = sum(k_values[-d_period:]) / d_period
                oversold = float(params.get("oversold", 20))
                overbought = float(params.get("overbought", 80))
                vote = "LONG" if k <= oversold and k > d else "SHORT" if k >= overbought and k < d else vote
                detail = f"%K {k:.1f} / %D {d:.1f}"
        votes.append({
            "name": name,
            "vote": vote,
            "long_enabled": bool(item.get("long_enabled", True)),
            "short_enabled": bool(item.get("short_enabled", True)),
            "detail": detail,
        })
    return votes
