"""Deterministic local adapter for paper trading."""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from .base import ExchangeAdapter
from .models import Balance, Candle, OrderRequest, OrderResult, Position, Ticker


class PaperTradingAdapter(ExchangeAdapter):
    """A no-network adapter that accepts orders for local development."""

    def __init__(self, starting_balance: Decimal = Decimal("10000")) -> None:
        self._balance = Balance("USDT", starting_balance, starting_balance)
        self._positions: dict[str, Position] = {}
        self._orders: dict[str, OrderResult] = {}
        self._prices: dict[str, Decimal] = {}

    def get_balance(self, asset: str = "USDT") -> Balance:
        if asset != self._balance.asset:
            return Balance(asset, Decimal("0"), Decimal("0"))
        return self._balance

    def get_ticker(self, symbol: str) -> Ticker:
        position = self._positions.get(symbol)
        price = self._prices.get(symbol) or (position.mark_price if position else Decimal("100"))
        return Ticker(symbol, price, datetime.now(UTC))

    def get_candles(self, symbol: str, interval: str, limit: int = 200) -> list[Candle]:
        return []

    def get_symbols(self) -> list[str]:
        return []

    def get_exchange_info(self, symbol: str) -> dict:
        return {"symbol": symbol, "step_size": "0.001", "tick_size": "0.01", "min_notional": "5"}

    def get_position(self, symbol: str) -> Position | None:
        return self._positions.get(symbol)

    def place_order(self, request: OrderRequest) -> OrderResult:
        order_id = str(uuid4())
        fill_price = request.price or Decimal("100")
        if request.order_type.value in {"STOP_MARKET", "TAKE_PROFIT_MARKET"}:
            result = OrderResult(
                order_id,
                request.symbol,
                "NEW",
                Decimal("0"),
                None,
                {"stopPrice": str(request.stop_price), "side": request.side.value},
            )
            self._orders[order_id] = result
            return result
        current = self._positions.get(request.symbol)
        if current and current.side != request.side:
            pnl = (fill_price - current.entry_price) * current.quantity
            if current.side.value == "SELL":
                pnl = -pnl
            self._balance = Balance(
                self._balance.asset,
                self._balance.wallet_balance + pnl,
                self._balance.available_balance + pnl,
            )
            if request.quantity >= current.quantity:
                self._positions.pop(request.symbol)
            else:
                self._positions[request.symbol] = Position(
                    current.symbol, current.side, current.quantity - request.quantity,
                    current.entry_price, fill_price, current.leverage,
                )
        else:
            self._positions[request.symbol] = Position(
                request.symbol, request.side, request.quantity, fill_price, fill_price, 1
            )
        result = OrderResult(order_id, request.symbol, "FILLED", request.quantity, fill_price)
        self._orders[order_id] = result
        return result

    def update_market_price(self, symbol: str, price: Decimal) -> None:
        """Advance paper price and fill triggered conditional orders."""
        if price <= 0:
            raise ValueError("market price must be positive")
        self._prices[symbol] = price
        for order in list(self._orders.values()):
            current_order = self._orders.get(order.order_id)
            if current_order is None or current_order.symbol != symbol or current_order.status != "NEW":
                continue
            stop_price = Decimal(current_order.raw["stopPrice"])
            should_fill = (current_order.raw["side"] == "SELL" and price <= stop_price) or (current_order.raw["side"] == "BUY" and price >= stop_price)
            if should_fill:
                position = self._positions.get(symbol)
                quantity = position.quantity if position else Decimal("0")
                if position:
                    pnl = (price - position.entry_price) * quantity
                    if position.side.value == "SELL":
                        pnl = -pnl
                    self._balance = Balance(self._balance.asset, self._balance.wallet_balance + pnl, self._balance.available_balance + pnl)
                    self._positions.pop(symbol)
                self._orders[order.order_id] = OrderResult(order.order_id, symbol, "FILLED", quantity, price, current_order.raw)
                for sibling in list(self._orders.values()):
                    if sibling.symbol == symbol and sibling.order_id != order.order_id and sibling.status == "NEW":
                        self.cancel_order(symbol, sibling.order_id)

    def get_open_orders(self, symbol: str | None = None) -> list[OrderResult]:
        return [order for order in self._orders.values() if order.status not in {"FILLED", "CANCELED"} and (symbol is None or order.symbol == symbol)]

    def get_order_status(self, symbol: str, order_id: str) -> OrderResult:
        order = self._orders.get(order_id)
        if order is None or order.symbol != symbol:
            raise KeyError(f"unknown order {order_id}")
        return order

    def cancel_order(self, symbol: str, order_id: str) -> None:
        order = self.get_order_status(symbol, order_id)
        self._orders[order_id] = OrderResult(order.order_id, order.symbol, "CANCELED", order.executed_quantity, order.average_price, order.raw)

    def cancel_all_orders(self, symbol: str) -> None:
        for order in list(self._orders.values()):
            if order.symbol == symbol and order.status not in {"FILLED", "CANCELED"}:
                self.cancel_order(symbol, order.order_id)

    def set_leverage(self, symbol: str, leverage: int) -> None:
        if leverage < 1:
            raise ValueError("leverage must be at least 1")

    def health_check(self) -> bool:
        return True
