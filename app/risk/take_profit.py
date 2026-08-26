"""Risk/reward take-profit calculations."""

from decimal import Decimal


class TakeProfitCalculator:
    def risk_reward(self, entry_price: Decimal, stop_price: Decimal, side: str, ratio: Decimal = Decimal("2")) -> Decimal:
        if ratio <= 0:
            raise ValueError("risk/reward ratio must be positive")
        distance = abs(entry_price - stop_price)
        if distance <= 0:
            raise ValueError("stop price must differ from entry price")
        return entry_price + distance * ratio if side == "BUY" else entry_price - distance * ratio