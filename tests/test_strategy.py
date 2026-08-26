from datetime import datetime, timedelta, timezone
from decimal import Decimal
from app.exchange.models import Candle
from app.signals import SignalSide
from app.strategy import IndicatorStrategy


def candles(values: list[int]) -> list[Candle]:
    start = datetime.now(timezone.utc)
    return [Candle(start + timedelta(minutes=index), Decimal(value), Decimal(value), Decimal(value), Decimal(value), Decimal("1"), start + timedelta(minutes=index + 1)) for index, value in enumerate(values)]


def test_strategy_holds_until_it_has_enough_data():
    signal = IndicatorStrategy().generate_signal("BTCUSDT", candles([100, 101]))
    assert signal.side is SignalSide.HOLD


def test_strategy_generates_buy_for_rising_market():
    signal = IndicatorStrategy(ema_fast=3, ema_slow=5, rsi_period=3, bb_period=5, adx_period=3).generate_signal("BTCUSDT", candles([100, 101, 102, 103, 104, 105]))
    assert signal.side is SignalSide.BUY
    assert signal.confidence > 0
    assert "macd" in signal.metadata
    assert "adx" in signal.metadata