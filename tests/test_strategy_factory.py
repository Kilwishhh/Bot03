from app.config import Settings
from app.strategy import IndicatorStrategy, create_strategy


def test_strategy_factory_uses_configured_indicator_periods():
    strategy = create_strategy(Settings(ema_fast=3, ema_slow=5, rsi_period=3, bb_period=5, adx_period=3))
    assert isinstance(strategy, IndicatorStrategy)
    assert strategy.ema_fast == 3