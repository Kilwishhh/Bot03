"""Simple operational health summary."""

from dataclasses import dataclass

from app.exchange.base import ExchangeAdapter
from app.exchange.models import Candle
from app.market_data import MarketDataHealth


@dataclass(frozen=True)
class HealthReport:
    exchange_reachable: bool
    market_data_fresh: bool
    market_data_ordered: bool

    @property
    def healthy(self) -> bool:
        return self.exchange_reachable and self.market_data_fresh and self.market_data_ordered


def check_health(exchange: ExchangeAdapter, candles: list[Candle]) -> HealthReport:
    data_health = MarketDataHealth()
    return HealthReport(exchange.health_check(), data_health.is_fresh(candles), data_health.has_valid_sequence(candles))
