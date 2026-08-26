"""Exchange adapter contract."""

from abc import ABC, abstractmethod
from datetime import datetime
from decimal import Decimal
from .models import Balance, Candle, OrderRequest, OrderResult, Position, Ticker


class ExchangeAdapter(ABC):
    """Minimal contract shared by paper, testnet, and live adapters."""

    @abstractmethod
    def get_balance(self, asset: str = "USDT") -> Balance: ...

    @abstractmethod
    def get_ticker(self, symbol: str) -> Ticker: ...

    @abstractmethod
    def get_candles(self, symbol: str, interval: str, limit: int = 200) -> list[Candle]: ...

    @abstractmethod
    def get_symbols(self) -> list[str]: ...

    @abstractmethod
    def get_exchange_info(self, symbol: str) -> dict: ...

    @abstractmethod
    def get_position(self, symbol: str) -> Position | None: ...

    @abstractmethod
    def place_order(self, request: OrderRequest) -> OrderResult: ...

    @abstractmethod
    def get_open_orders(self, symbol: str | None = None) -> list[OrderResult]: ...

    @abstractmethod
    def get_order_status(self, symbol: str, order_id: str) -> OrderResult: ...

    @abstractmethod
    def cancel_order(self, symbol: str, order_id: str) -> None: ...

    @abstractmethod
    def cancel_all_orders(self, symbol: str) -> None: ...

    @abstractmethod
    def set_leverage(self, symbol: str, leverage: int) -> None: ...

    @abstractmethod
    def health_check(self) -> bool: ...
