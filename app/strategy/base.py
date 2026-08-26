"""Strategy contract with no exchange dependency."""

from abc import ABC, abstractmethod
from app.exchange.models import Candle
from app.signals.models import Signal


class Strategy(ABC):
    @abstractmethod
    def generate_signal(self, symbol: str, candles: list[Candle]) -> Signal:
        """Return a signal using only supplied market data."""