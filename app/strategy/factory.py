"""Safe registry for configured built-in strategies."""

from app.config import Settings
from .base import Strategy
from .indicator_strategy import IndicatorStrategy


def create_strategy(settings: Settings) -> Strategy:
    if settings.strategy == "indicator":
        return IndicatorStrategy(settings.ema_fast, settings.ema_slow, settings.rsi_period, settings.bb_period, settings.adx_period)
    raise ValueError(f"unsupported strategy: {settings.strategy}")