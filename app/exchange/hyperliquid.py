"""Read-only Hyperliquid market-data adapter.

Order signing is intentionally not implemented here. Wallet-connected execution
must be added through an official signing flow and explicit user approval.
"""

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from urllib.request import Request, urlopen

from app.monitoring.retry import retry_read

from .base import ExchangeAdapter
from .models import Balance, Candle, OrderRequest, OrderResult, Position, Ticker


@dataclass(frozen=True)
class OrderPreview:
    symbol: str
    side: str
    order_type: str
    quantity: Decimal
    price: Decimal | None
    requires_approval: bool = True
    status: str = "pending_approval"
    wallet_address: str = ""
    client_order_id: str = ""


class HyperliquidAdapter(ExchangeAdapter):
    def __init__(self, api_url: str = "https://api.hyperliquid.xyz", wallet_address: str = "") -> None:
        self._api_url = api_url.rstrip("/")
        self._wallet_address = wallet_address
        self._approved_orders: set[str] = set()

    def _info(self, payload: dict) -> object:
        request = Request(f"{self._api_url}/info", data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"}, method="POST")
        return retry_read(lambda: self._read_info(request))

    def preview_order(self, request: OrderRequest) -> OrderPreview:
        if not self._wallet_address:
            raise NotImplementedError("Hyperliquid order signing requires wallet approval")
        return OrderPreview(
            symbol=request.symbol,
            side=request.side.value,
            order_type=request.order_type.value,
            quantity=request.quantity,
            price=request.price,
            requires_approval=True,
            status="pending_approval",
            wallet_address=self._wallet_address,
            client_order_id=request.client_order_id or f"{request.symbol}:{request.side.value}:{request.quantity}:{request.price or 0}",
        )

    def approve_order(self, item: OrderPreview | OrderRequest) -> None:
        if not self._wallet_address:
            raise NotImplementedError("Hyperliquid order signing requires wallet approval")
        if isinstance(item, OrderPreview):
            key = item.wallet_address + ":" + (item.client_order_id or f"{item.symbol}:{item.side}:{item.quantity}:{item.price or 0}")
        else:
            key = item.client_order_id or f"{item.symbol}:{item.side.value}:{item.quantity}:{item.price or 0}"
            key = self._wallet_address + ":" + key
        self._approved_orders.add(key)

    @staticmethod
    def _read_info(request: Request) -> object:
        with urlopen(request, timeout=10) as response:
            return json.loads(response.read())

    def get_balance(self, asset: str = "USDC") -> Balance:
        if not self._wallet_address:
            return Balance(asset, Decimal("0"), Decimal("0"))
        state = self._info({"type": "clearinghouseState", "user": self._wallet_address})
        balance = next((item for item in state.get("marginSummary", {}).items() if item[0] == "accountValue"), ("accountValue", "0"))[1]
        return Balance(asset, Decimal(str(balance)), Decimal(str(balance)))

    def get_ticker(self, symbol: str) -> Ticker:
        prices = self._info({"type": "allMids"})
        return Ticker(symbol, Decimal(str(prices[symbol])), datetime.now(UTC))

    def get_candles(self, symbol: str, interval: str, limit: int = 200) -> list[Candle]:
        end = int(datetime.now(UTC).timestamp() * 1000)
        rows = self._info({"type": "candleSnapshot", "req": {"coin": symbol, "interval": interval, "startTime": 0, "endTime": end}})
        return [Candle(datetime.fromtimestamp(row["t"] / 1000, UTC), Decimal(row["o"]), Decimal(row["h"]), Decimal(row["l"]), Decimal(row["c"]), Decimal(row["v"]), datetime.fromtimestamp(row["T"] / 1000, UTC)) for row in rows[-limit:]]

    def get_symbols(self) -> list[str]:
        metadata = self._info({"type": "meta"})
        return [item["name"] for item in metadata.get("universe", []) if not item.get("isDelisted", False)]

    def get_exchange_info(self, symbol: str) -> dict:
        return {"symbol": symbol, "step_size": "0.0001", "tick_size": "0.01", "min_notional": "0"}

    def get_position(self, symbol: str) -> Position | None:
        if not self._wallet_address:
            raise NotImplementedError("Hyperliquid account positions require a wallet address")
        raise NotImplementedError("Hyperliquid position mapping is pending signed-wallet integration")

    def place_order(self, request: OrderRequest) -> OrderResult:
        if not self._wallet_address:
            raise NotImplementedError("Hyperliquid order signing requires wallet approval")
        order_key = request.client_order_id or f"{request.symbol}:{request.side.value}:{request.quantity}:{request.price or 0}"
        approval_key = self._wallet_address + ":" + order_key
        if approval_key not in self._approved_orders:
            raise RuntimeError("Hyperliquid order requires explicit wallet approval before signing")
        return OrderResult(
            order_id=order_key,
            symbol=request.symbol,
            status="approved",
            executed_quantity=request.quantity,
            average_price=request.price,
            raw={"approved": True, "wallet_address": self._wallet_address},
        )

    def get_open_orders(self, symbol: str | None = None) -> list[OrderResult]:
        raise NotImplementedError("Hyperliquid account queries require wallet integration")

    def get_order_status(self, symbol: str, order_id: str) -> OrderResult:
        raise NotImplementedError("Hyperliquid order status requires wallet integration")

    def cancel_order(self, symbol: str, order_id: str) -> None:
        raise NotImplementedError("Hyperliquid order signing requires wallet approval")

    def cancel_all_orders(self, symbol: str) -> None:
        raise NotImplementedError("Hyperliquid order signing requires wallet approval")

    def set_leverage(self, symbol: str, leverage: int) -> None:
        raise NotImplementedError("Hyperliquid leverage signing requires wallet approval")

    def health_check(self) -> bool:
        self._info({"type": "meta"})
        return True
