"""Binance-compatible quantity and price step normalization."""

from decimal import Decimal, ROUND_DOWN


def normalize(value: Decimal, step: Decimal) -> Decimal:
    if value <= 0 or step <= 0:
        raise ValueError("value and step must be positive")
    return (value / step).to_integral_value(rounding=ROUND_DOWN) * step


def validate_step(value: Decimal, step: Decimal, field: str) -> None:
    if normalize(value, step) != value:
        raise ValueError(f"{field} does not match exchange step size")