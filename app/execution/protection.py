"""Create and clean up paired stop-loss and take-profit protection."""

from app.exchange.base import ExchangeAdapter
from app.exchange.models import OrderRequest, OrderResult, OrderSide, OrderType, Position
from .order_validator import validate_order


class ProtectionManager:
    def __init__(self, exchange: ExchangeAdapter) -> None:
        self._exchange = exchange

    def protect(self, position: Position, stop_price, take_profit_price) -> tuple[OrderResult, OrderResult]:
        exit_side = OrderSide.SELL if position.side is OrderSide.BUY else OrderSide.BUY
        stop = OrderRequest(position.symbol, exit_side, OrderType.STOP_MARKET, position.quantity, stop_price=stop_price)
        target = OrderRequest(position.symbol, exit_side, OrderType.TAKE_PROFIT_MARKET, position.quantity, stop_price=take_profit_price)
        validate_order(stop)
        validate_order(target)
        stop_result = self._exchange.place_order(stop)
        try:
            target_result = self._exchange.place_order(target)
        except Exception:
            self._exchange.cancel_order(position.symbol, stop_result.order_id)
            raise
        return stop_result, target_result