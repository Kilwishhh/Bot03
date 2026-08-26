"""Binance Futures adapter. Credentials are supplied only through settings."""

from datetime import datetime, timezone
from decimal import Decimal
from .base import ExchangeAdapter
from .models import Balance, Candle, OrderRequest, OrderResult, OrderSide, Position, Ticker
from app.monitoring.retry import retry_read


class BinanceFuturesAdapter(ExchangeAdapter):
    """Thin adapter around python-binance; trading mode selection lives above it."""

    def __init__(self, api_key: str, api_secret: str, testnet: bool = True) -> None:
        from binance.client import Client
        self._client = Client(api_key, api_secret, testnet=testnet)

    def get_balance(self, asset: str = "USDT") -> Balance:
        row = next(item for item in self._client.futures_account_balance() if item["asset"] == asset)
        return Balance(asset, Decimal(row["balance"]), Decimal(row["availableBalance"]))

    def get_ticker(self, symbol: str) -> Ticker:
        row = retry_read(lambda: self._client.futures_symbol_ticker(symbol=symbol))
        return Ticker(symbol, Decimal(row["price"]), datetime.now(timezone.utc))

    def get_candles(self, symbol: str, interval: str, limit: int = 200) -> list[Candle]:
        rows = retry_read(lambda: self._client.futures_klines(symbol=symbol, interval=interval, limit=limit))
        return [Candle(
            datetime.fromtimestamp(row[0] / 1000, timezone.utc), Decimal(row[1]), Decimal(row[2]),
            Decimal(row[3]), Decimal(row[4]), Decimal(row[5]),
            datetime.fromtimestamp(row[6] / 1000, timezone.utc),
        ) for row in rows]

    def get_symbols(self) -> list[str]:
        exchange_info = retry_read(self._client.futures_exchange_info)
        return [
            item["symbol"] for item in exchange_info["symbols"]
            if item["status"] == "TRADING"
            and item["quoteAsset"] == "USDT"
            and item["contractType"] == "PERPETUAL"
        ]

    def get_exchange_info(self, symbol: str) -> dict:
        row = next(item for item in self._client.futures_exchange_info()["symbols"] if item["symbol"] == symbol)
        filters = {item["filterType"]: item for item in row["filters"]}
        return {"symbol": symbol, "step_size": filters["LOT_SIZE"]["stepSize"], "tick_size": filters["PRICE_FILTER"]["tickSize"], "min_notional": filters.get("MIN_NOTIONAL", {}).get("notional", "0")}

    def get_position(self, symbol: str) -> Position | None:
        rows = self._client.futures_position_information(symbol=symbol)
        row = rows[0] if rows else None
        if not row or Decimal(row["positionAmt"]) == 0:
            return None
        amount = Decimal(row["positionAmt"])
        side = OrderSide.BUY if amount > 0 else OrderSide.SELL
        return Position(symbol, side, abs(amount), Decimal(row["entryPrice"]), Decimal(row["markPrice"]), int(row["leverage"]), Decimal(row["unRealizedProfit"]))

    def place_order(self, request: OrderRequest) -> OrderResult:
        payload = {"symbol": request.symbol, "side": request.side.value, "type": request.order_type.value, "quantity": str(request.quantity)}
        if request.price is not None:
            payload["price"] = str(request.price)
        if request.stop_price is not None:
            payload["stopPrice"] = str(request.stop_price)
        if request.client_order_id:
            payload["newClientOrderId"] = request.client_order_id
        row = self._client.futures_create_order(**payload)
        return OrderResult(str(row["orderId"]), request.symbol, row["status"], Decimal(row.get("executedQty", "0")), None, row)

    def get_open_orders(self, symbol: str | None = None) -> list[OrderResult]:
        rows = self._client.futures_get_open_orders(symbol=symbol) if symbol else self._client.futures_get_open_orders()
        return [OrderResult(str(row["orderId"]), row["symbol"], row["status"], Decimal(row.get("executedQty", "0")), None, row) for row in rows]

    def get_order_status(self, symbol: str, order_id: str) -> OrderResult:
        row = self._client.futures_get_order(symbol=symbol, orderId=order_id)
        return OrderResult(str(row["orderId"]), symbol, row["status"], Decimal(row.get("executedQty", "0")), None, row)

    def cancel_order(self, symbol: str, order_id: str) -> None:
        self._client.futures_cancel_order(symbol=symbol, orderId=order_id)

    def cancel_all_orders(self, symbol: str) -> None:
        self._client.futures_cancel_all_open_orders(symbol=symbol)

    def set_leverage(self, symbol: str, leverage: int) -> None:
        if leverage < 1:
            raise ValueError("leverage must be at least 1")
        self._client.futures_change_leverage(symbol=symbol, leverage=leverage)

    def health_check(self) -> bool:
        self._client.futures_ping()
        return True
