"""Stop-loss calculations."""

from decimal import Decimal


class StopLossCalculator:
    def percentage(self, entry_price: Decimal, side: str, distance: Decimal) -> Decimal:
        if entry_price <= 0 or distance <= 0:
            raise ValueError("entry price and distance must be positive")
        return entry_price - distance if side == "BUY" else entry_price + distance
