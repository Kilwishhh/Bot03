"""Exchange-neutral data models."""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any


class OrderSide(StrEnum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(StrEnum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP_MARKET = "STOP_MARKET"
    TAKE_PROFIT_MARKET = "TAKE_PROFIT_MARKET"


@dataclass(frozen=True)
class Candle:
    open_time: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    close_time: datetime


@dataclass(frozen=True)
class Ticker:
    symbol: str
    price: Decimal
    timestamp: datetime


@dataclass(frozen=True)
class Balance:
    asset: str
    wallet_balance: Decimal
    available_balance: Decimal


@dataclass(frozen=True)
class Position:
    symbol: str
    side: OrderSide
    quantity: Decimal
    entry_price: Decimal
    mark_price: Decimal
    leverage: int
    unrealized_pnl: Decimal = Decimal("0")


@dataclass(frozen=True)
class OrderRequest:
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: Decimal
    price: Decimal | None = None
    stop_price: Decimal | None = None
    client_order_id: str | None = None


@dataclass(frozen=True)
class OrderResult:
    order_id: str
    symbol: str
    status: str
    executed_quantity: Decimal
    average_price: Decimal | None = None
    raw: dict[str, Any] = field(default_factory=dict)
