"""Detect local/exchange position desynchronization before trading continues."""

from dataclasses import dataclass
from decimal import Decimal
from app.exchange.base import ExchangeAdapter
from app.exchange.models import Position


@dataclass(frozen=True)
class ReconciliationResult:
    synchronized: bool
    reason: str


class Reconciler:
    def __init__(self, exchange: ExchangeAdapter) -> None:
        self._exchange = exchange
        self.trading_blocked = False

    def compare_position(self, expected: Position | None, symbol: str) -> ReconciliationResult:
        actual = self._exchange.get_position(symbol)
        if self._same_position(expected, actual):
            return ReconciliationResult(True, "position synchronized")
        self.trading_blocked = True
        return ReconciliationResult(False, "local and exchange positions differ; trading blocked")

    @staticmethod
    def _same_position(expected: Position | None, actual: Position | None) -> bool:
        if expected is None or actual is None:
            return expected is actual
        return expected.symbol == actual.symbol and expected.side == actual.side and abs(expected.quantity - actual.quantity) <= Decimal("0.00000001") and abs(expected.entry_price - actual.entry_price) <= Decimal("0.00000001")