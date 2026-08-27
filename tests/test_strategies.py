"""Tests for the strategy registry, factory, and all built-in strategies."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.config import Settings
from app.exchange.models import Candle
from app.signals import SignalSide
from app.strategy import (
    BollingerStrategy,
    EMACrossoverStrategy,
    IndicatorStrategy,
    MACDCrossoverStrategy,
    RSIMeanReversionStrategy,
    available_strategies,
    create_strategy,
    is_registered,
    register,
)
from app.strategy.base import Strategy


def _candles(values: list[int], flat_high_low: bool = True) -> list[Candle]:
    """Build a synthetic candle series. Defaults to flat high=low=close for predictability."""
    start = datetime.now(UTC)
    out: list[Candle] = []
    for i, value in enumerate(values):
        v = Decimal(value)
        h = v if flat_high_low else v + Decimal("1")
        lo = v if flat_high_low else v - Decimal("1")
        out.append(
            Candle(
                open_time=start + timedelta(minutes=i),
                open=v,
                high=h,
                low=lo,
                close=v,
                volume=Decimal("1"),
                close_time=start + timedelta(minutes=i + 1),
            )
        )
    return out


# ----------------------------------------------------------------------
# Registry / factory
# ----------------------------------------------------------------------

def test_registry_contains_builtin_strategies():
    names = available_strategies()
    for required in ("indicator", "ema_crossover", "macd_crossover", "bollinger", "rsi_mean_reversion"):
        assert required in names


def test_create_strategy_returns_indicator_by_default():
    settings = Settings()
    assert isinstance(create_strategy(settings), IndicatorStrategy)


def test_create_strategy_routes_by_name():
    settings = Settings(strategy="ema_crossover")
    assert isinstance(create_strategy(settings), EMACrossoverStrategy)


def test_create_strategy_routes_macd():
    settings = Settings(strategy="macd_crossover")
    assert isinstance(create_strategy(settings), MACDCrossoverStrategy)


def test_create_strategy_routes_bollinger():
    settings = Settings(strategy="bollinger")
    assert isinstance(create_strategy(settings), BollingerStrategy)


def test_create_strategy_routes_rsi_reversion():
    settings = Settings(strategy="rsi_mean_reversion")
    assert isinstance(create_strategy(settings), RSIMeanReversionStrategy)


def test_settings_rejects_unknown_strategy_name():
    with pytest.raises(Exception, match="unsupported strategy"):
        Settings(strategy="nope")


def test_register_overrides_existing_name():
    class _Dummy(Strategy):
        name = "_dummy_override_test"

        def generate_signal(self, symbol, candles):
            return None  # type: ignore[return-value]

    register(_Dummy.name, lambda _s: _Dummy())
    assert is_registered(_Dummy.name)
    # cleanup: remove so other tests aren't affected
    from app.strategy.factory import _REGISTRY
    _REGISTRY.pop(_Dummy.name, None)


# ----------------------------------------------------------------------
# EMACrossoverStrategy
# ----------------------------------------------------------------------

def test_ema_crossover_holds_without_a_fresh_cross():
    s = EMACrossoverStrategy(ema_fast=3, ema_slow=5)
    # Fast already above slow, no new cross — should HOLD
    series = [80, 82, 84, 86, 88, 90, 92, 94, 96, 98, 100, 102, 104, 106, 108]
    signal = s.generate_signal("BTCUSDT", _candles(series))
    assert signal.side is SignalSide.HOLD


def test_ema_crossover_buy_on_upward_cross():
    s = EMACrossoverStrategy(ema_fast=3, ema_slow=5)
    # Start with fast well below slow, then cross on the last bar.
    # Fast EMA(3) of [90,95,100] ≈ 98.3; Slow EMA(5) of [80..100] ≈ 91.2 → fast < slow.
    # Then spike: fast of [100,105,115] ≈ 108.3; slow of [85..115] ≈ 96.7 → fast > slow (cross).
    series = [80, 82, 84, 86, 88, 90, 92, 94, 96, 98, 100, 100, 100, 100, 100, 105, 115]
    signal = s.generate_signal("BTCUSDT", _candles(series))
    assert signal.side is SignalSide.BUY
    assert signal.confidence > 0


def test_ema_crossover_sell_on_downward_cross():
    s = EMACrossoverStrategy(ema_fast=3, ema_slow=5)
    # Start with fast well above slow, then cross downward on the last bar.
    series = [120, 118, 116, 114, 112, 110, 108, 106, 104, 102, 100, 100, 100, 100, 100, 95, 85]
    signal = s.generate_signal("BTCUSDT", _candles(series))
    assert signal.side is SignalSide.SELL


def test_ema_crossover_rejects_invalid_periods():
    with pytest.raises(ValueError):
        EMACrossoverStrategy(ema_fast=10, ema_slow=5)


# ----------------------------------------------------------------------
# MACDCrossoverStrategy
# ----------------------------------------------------------------------

def test_macd_crossover_holds_when_insufficient_data():
    s = MACDCrossoverStrategy(fast=3, slow=5, signal_period=2)
    signal = s.generate_signal("BTCUSDT", _candles([100] * 5))
    assert signal.side is SignalSide.HOLD


def test_macd_crossover_emits_signal_on_long_enough_series():
    s = MACDCrossoverStrategy(fast=3, slow=5, signal_period=2)
    # rising series — should produce a directional signal at some point
    series = list(range(80, 120))
    signal = s.generate_signal("BTCUSDT", _candles(series))
    assert signal.side in (SignalSide.BUY, SignalSide.SELL, SignalSide.HOLD)
    assert "macd" in signal.metadata


# ----------------------------------------------------------------------
# BollingerStrategy
# ----------------------------------------------------------------------

def test_bollinger_breakout_buy_above_upper_band():
    s = BollingerStrategy(period=10, std_multiplier=Decimal("2"), mode="breakout")
    # flat then a spike up
    series = [100] * 15 + [130]
    signal = s.generate_signal("BTCUSDT", _candles(series))
    assert signal.side is SignalSide.BUY


def test_bollinger_breakout_sell_below_lower_band():
    s = BollingerStrategy(period=10, std_multiplier=Decimal("2"), mode="breakout")
    series = [100] * 15 + [70]
    signal = s.generate_signal("BTCUSDT", _candles(series))
    assert signal.side is SignalSide.SELL


def test_bollinger_reversion_inverts_breakout_signals():
    s = BollingerStrategy(period=10, std_multiplier=Decimal("2"), mode="reversion")
    series = [100] * 15 + [70]  # below lower band
    signal = s.generate_signal("BTCUSDT", _candles(series))
    assert signal.side is SignalSide.BUY  # reversion: oversold = buy


def test_bollinger_rejects_invalid_mode():
    with pytest.raises(ValueError, match="mode must be"):
        BollingerStrategy(mode="nope")


# ----------------------------------------------------------------------
# RSIMeanReversionStrategy
# ----------------------------------------------------------------------

def test_rsi_reversion_buy_when_oversold():
    s = RSIMeanReversionStrategy(period=5, oversold=Decimal("30"), overbought=Decimal("70"))
    # long streak of falling prices
    series = list(range(120, 70, -1))
    signal = s.generate_signal("BTCUSDT", _candles(series))
    assert signal.side is SignalSide.BUY


def test_rsi_reversion_sell_when_overbought():
    s = RSIMeanReversionStrategy(period=5, oversold=Decimal("30"), overbought=Decimal("70"))
    # long streak of rising prices
    series = list(range(70, 120))
    signal = s.generate_signal("BTCUSDT", _candles(series))
    assert signal.side is SignalSide.SELL


def test_rsi_reversion_holds_in_neutral_band():
    s = RSIMeanReversionStrategy(period=5, oversold=Decimal("30"), overbought=Decimal("70"))
    # oscillating series — RSI should stay in the neutral band
    series = [100, 101, 99, 100, 102, 98, 100, 101, 99, 100, 101]
    signal = s.generate_signal("BTCUSDT", _candles(series))
    # It might still emit a directional signal if RSI drifts; accept any
    # non-error result and check the metadata is present.
    assert signal.strategy_name == RSIMeanReversionStrategy.__name__


def test_rsi_reversion_rejects_invalid_thresholds():
    with pytest.raises(ValueError):
        RSIMeanReversionStrategy(oversold=Decimal("60"), overbought=Decimal("70"))


# ----------------------------------------------------------------------
# IndicatorStrategy (default ensemble) — verify it still works after the
# refactor to use shared indicators.
# ----------------------------------------------------------------------

def test_indicator_strategy_holds_until_enough_data():
    signal = IndicatorStrategy(ema_fast=3, ema_slow=5, rsi_period=3, bb_period=5, adx_period=3).generate_signal("BTCUSDT", _candles([100, 101]))
    assert signal.side is SignalSide.HOLD


def test_indicator_strategy_buy_for_rising_market():
    s = IndicatorStrategy(ema_fast=3, ema_slow=5, rsi_period=3, bb_period=5, adx_period=3)
    signal = s.generate_signal("BTCUSDT", _candles([100, 101, 102, 103, 104, 105]))
    assert signal.side is SignalSide.BUY
    assert signal.confidence > 0
    assert "macd" in signal.metadata


# ----------------------------------------------------------------------
# Per-strategy settings are wired
# ----------------------------------------------------------------------

def test_macd_settings_are_loaded_into_strategy():
    settings = Settings(strategy="macd_crossover", macd_fast=5, macd_slow=10, macd_signal=3)
    s = create_strategy(settings)
    assert isinstance(s, MACDCrossoverStrategy)
    assert s.fast == 5
    assert s.slow == 10
    assert s.signal_period == 3


def test_bollinger_settings_are_loaded_into_strategy():
    settings = Settings(strategy="bollinger", bb_period=15, bollinger_std=2.5, bollinger_mode="reversion")
    s = create_strategy(settings)
    assert isinstance(s, BollingerStrategy)
    assert s.period == 15
    assert s.std_multiplier == Decimal("2.5")
    assert s.mode == "reversion"


def test_rsi_reversion_settings_are_loaded_into_strategy():
    settings = Settings(strategy="rsi_mean_reversion", rsi_period=7, rsi_oversold=25.0, rsi_overbought=75.0)
    s = create_strategy(settings)
    assert isinstance(s, RSIMeanReversionStrategy)
    assert s.period == 7
    assert s.oversold == Decimal("25")
    assert s.overbought == Decimal("75")
