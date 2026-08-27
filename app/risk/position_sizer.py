"""Risk-based position sizing with conservative quantity limits."""

from decimal import ROUND_DOWN, Decimal


class PositionSizer:
    def __init__(self, risk_per_trade: Decimal, step_size: Decimal = Decimal("0.001")) -> None:
        if risk_per_trade <= 0:
            raise ValueError("risk per trade must be positive")
        self.risk_per_trade = risk_per_trade
        self.step_size = step_size

    def calculate(self, balance: Decimal, entry_price: Decimal, stop_price: Decimal) -> Decimal:
        distance = abs(entry_price - stop_price)
        if balance <= 0 or entry_price <= 0 or distance <= 0:
            raise ValueError("balance, entry price, and stop distance must be positive")
        raw_quantity = balance * self.risk_per_trade / distance
        return (raw_quantity / self.step_size).to_integral_value(rounding=ROUND_DOWN) * self.step_size
