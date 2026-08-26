"""Fee-aware realized and unrealized PnL calculations."""

from dataclasses import dataclass
from decimal import Decimal
from app.exchange.models import OrderSide, Position


@dataclass(frozen=True)
class PnlSummary:
    gross: Decimal
    fees: Decimal
    funding: Decimal = Decimal("0")

    @property
    def net(self) -> Decimal:
        return self.gross - self.fees - self.funding


class PnlCalculator:
    def realized(self, side: OrderSide, entry_price: Decimal, exit_price: Decimal, quantity: Decimal, fees: Decimal = Decimal("0"), funding: Decimal = Decimal("0")) -> PnlSummary:
        gross = (exit_price - entry_price) * quantity
        if side is OrderSide.SELL:
            gross = -gross
        return PnlSummary(gross, fees, funding)

    def unrealized(self, position: Position, fees: Decimal = Decimal("0"), funding: Decimal = Decimal("0")) -> PnlSummary:
        gross = (position.mark_price - position.entry_price) * position.quantity
        if position.side is OrderSide.SELL:
            gross = -gross
        return PnlSummary(gross, fees, funding)