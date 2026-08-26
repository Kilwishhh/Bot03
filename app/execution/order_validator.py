"""Validation rules applied before an order reaches an exchange."""

from decimal import Decimal
from app.exchange.models import OrderRequest, OrderType


class OrderValidationError(ValueError):
    """Raised when an order cannot be safely submitted."""


def validate_order(request: OrderRequest) -> None:
    """Validate exchange-independent order requirements."""
    if not request.symbol.strip():
        raise OrderValidationError("symbol is required")
    if request.quantity <= Decimal("0"):
        raise OrderValidationError("quantity must be positive")
    if request.order_type is OrderType.LIMIT and request.price is None:
        raise OrderValidationError("limit orders require a price")
    if request.order_type in (OrderType.STOP_MARKET, OrderType.TAKE_PROFIT_MARKET) and request.stop_price is None:
        raise OrderValidationError("conditional orders require a stop price")
    if request.price is not None and request.price <= Decimal("0"):
        raise OrderValidationError("price must be positive")
    if request.stop_price is not None and request.stop_price <= Decimal("0"):
        raise OrderValidationError("stop price must be positive")