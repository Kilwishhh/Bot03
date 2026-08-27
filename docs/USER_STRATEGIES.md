# User-Defined Strategies

MK TRADER auto-loads any Python strategy dropped into `app/strategy/user_strategies/` on import. No registration calls or config changes are needed — just drop the file and restart.

---

## How it works

`app/strategy/factory.py` runs `_load_user_strategies()` at import time. It walks `user_strategies/` and registers every `Strategy` subclass it finds (or module that exposes a `build(settings)` function).

---

## Option A — Strategy subclass with a `name` attribute

Best for strategies that don't need settings from the environment.

```python
# app/strategy/user_strategies/my_breakout.py
from datetime import datetime, timezone
from app.exchange.models import Candle
from app.signals.models import Signal, SignalSide
from app.strategy.base import Strategy


class MyBreakoutStrategy(Strategy):
    """Buy when price breaks above yesterday's high, sell otherwise."""

    name = "my_breakout"

    def __init__(self, lookback: int = 20) -> None:
        self.lookback = lookback

    def generate_signal(self, symbol: str, candles: list[Candle]) -> Signal:
        timestamp = candles[-1].close_time if candles else datetime.now(timezone.utc)
        base = dict(symbol=symbol, timestamp=timestamp, strategy_name="MyBreakoutStrategy")

        if len(candles) < self.lookback:
            return Signal(**base, side=SignalSide.HOLD, confidence=0.0, reason=["insufficient candles"])

        closes = [c.close for c in candles]
        recent_high = max(closes[-self.lookback:])
        last_close = closes[-1]

        if last_close > recent_high:
            return Signal(**base, side=SignalSide.BUY, confidence=0.8,
                          reason=[f"close {last_close} > {self.lookback}-candle high {recent_high}"])
        return Signal(**base, side=SignalSide.SELL, confidence=0.6,
                      reason=[f"close {last_close} <= {self.lookback}-candle high {recent_high}"])
```

The class's `name = "my_breakout"` becomes the strategy key. Set `STRATEGY=my_breakout` in `.env` to use it.

**Constructor args** — if your `__init__` takes arguments, the factory calls it with no args. Put all defaults in `__init__`:

```python
def __init__(self, lookback: int = 20) -> None:   # 20 is the default
    self.lookback = lookback
```

---

## Option B — `build(settings)` function

Best for strategies that need values from the environment.

```python
# app/strategy/user_strategies/my_pullback.py
from app.config import Settings
from app.strategy.base import Strategy


class MyPullbackStrategy(Strategy):
    name = "my_pullback"

    def __init__(self, threshold: float) -> None:
        self.threshold = threshold

    def generate_signal(self, symbol, candles):
        # ... signal logic using self.threshold
        ...


def build(settings: Settings):
    # Read from env, provide defaults
    return MyPullbackStrategy(threshold=float(getattr(settings, "pullback_threshold", "0.5")))
```

The module-level `build(settings)` is called instead of the default no-arg constructor.

---

## Shared indicator helpers

All strategies can import the shared math helpers — no need to reimplement EMA, RSI, etc.:

```python
from app.strategy.indicators import (
    ema, rsi, macd, bollinger_bands, atr, sma,
)
```

See `app/strategy/indicators.py` for the full list and signatures.

---

## Built-in strategy names for reference

| Name                | Class                   | Description                       |
| ------------------- | ----------------------- | --------------------------------- |
| `indicator`         | `IndicatorStrategy`     | EMA + RSI + ADX composite         |
| `ema_crossover`     | `EMACrossoverStrategy` | Fast/slow EMA crossover           |
| `macd_crossover`   | `MACDCrossoverStrategy` | MACD / signal line crossover      |
| `bollinger`         | `BollingerStrategy`     | Bollinger band breakout/reversion |
| `rsi_mean_reversion`| `RSIMeanReversionStrategy` | RSI overbought/oversold fades |

---

## Disabling a strategy temporarily

Rename the file with a leading underscore — it will be skipped on the next startup:

```
app/strategy/user_strategies/my_breakout.py   ← active
app/strategy/user_strategies/_my_breakout.py  ← disabled
```

---

## Debugging

If your strategy doesn't appear in `STRATEGY=<name>` at startup, check:

1. The file is under `app/strategy/user_strategies/`
2. The class inherits from `Strategy` (from `app.strategy.base`)
3. The class has a `name: str` class attribute
4. Or, the module has a top-level `build(settings)` function
5. Run `python -c "from app.strategy import factory; print(factory.available_strategies())"` to see what's registered

If there's an import error in your strategy file, the loader logs it and keeps the app running — but the strategy won't register.

---

## Shipping an example

The file `app/strategy/user_strategies/_my_first_strategy.py` is the shipped example. It is named with a leading underscore so it is not auto-selected as the default, but it IS auto-loaded under its class name `my_first_strategy`. Remove the leading underscore from the class name (and the file name) when you adapt it.
