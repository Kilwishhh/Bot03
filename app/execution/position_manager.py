"""Position lifecycle facade independent of the concrete exchange."""

from decimal import Decimal
from app.exchange.base import ExchangeAdapter
from app.exchange.models import OrderRequest, OrderResult, Position
from .order_validator import validate_order


class PositionManager:
    """Submit validated orders and read positions from an adapter."""

    def __init__(self, exchange: ExchangeAdapter) -> None:
        self._exchange = exchange

    def get(self, symbol: str) -> Position | None:
        return self._exchange.get_position(symbol)

    def submit(self, request: OrderRequest) -> OrderResult:
        validate_order(request)
        result = self._exchange.place_order(request)
        if result.status == "FILLED" and result.executed_quantity <= Decimal("0"):
            raise RuntimeError("exchange reported FILLED without executed quantity")
        return result