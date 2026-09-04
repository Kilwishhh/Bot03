"""Paper trading adapter: real Binance market data + simulated execution."""

from datetime import UTC, datetime
from decimal import Decimal
from threading import Lock
from uuid import uuid4

from .base import ExchangeAdapter
from .models import Balance, Candle, OrderRequest, OrderResult, Position, Ticker


class PaperTradingAdapter(ExchangeAdapter):
    """Paper trading: real Binance candles + simulated order/position/PnL.

    Market data (candles, ticker) comes from the Binance public API.
    No credentials needed for public market data.
    Orders, positions, and PnL are simulated locally.
    """

    _http_lock = Lock()
    # Paper execution accepts precise fractional quantities so a small
    # configured notional remains usable for high-priced symbols.
    allows_fractional_quantities = True

    def __init__(self, starting_balance: Decimal = Decimal("10000"), leverage: int = 1) -> None:
        if leverage < 1:
            raise ValueError("leverage must be at least 1")
        self._balance = Balance("USDT", starting_balance, starting_balance)
        self._positions: dict[str, Position] = {}
        self._orders: dict[str, OrderResult] = {}
        self._prices: dict[str, Decimal] = {}
        self._candle_cache: dict[str, tuple[float, list[Candle]]] = {}
        self._leverage = leverage

    # ── market data (real Binance public API) ────────────────────────────────

    def get_candles(self, symbol: str, interval: str, limit: int = 200) -> list[Candle]:
        """Fetch real candles from Binance public API. Cached for 30s to avoid rate limits."""
        now_ts = datetime.now(UTC).timestamp()
        cached_ts, cached = self._candle_cache.get(symbol, (0.0, []))
        if now_ts - cached_ts < 30 and cached:
            return cached
        try:
            import json, urllib.request
            url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"
            with self._http_lock:
                with urllib.request.urlopen(url, timeout=10) as resp:
                    rows = json.loads(resp.read())
            candles = [
                Candle(
                    open_time=datetime.fromtimestamp(row[0] / 1000, UTC),
                    open=Decimal(row[1]), high=Decimal(row[2]),
                    low=Decimal(row[3]), close=Decimal(row[4]),
                    close_time=datetime.fromtimestamp(row[6] / 1000, UTC),
                    volume=Decimal(row[5]),
                )
                for row in rows
            ]
            with self._http_lock:
                self._candle_cache[symbol] = (now_ts, candles)
            return candles
        except Exception:
            with self._http_lock:
                if cached:
                    return cached
            return []

    def get_ticker(self, symbol: str) -> Ticker:
        position = self._positions.get(symbol)
        cached = self._prices.get(symbol)
        if cached is not None:
            price = cached
        elif position is not None and position.mark_price is not None:
            price = position.mark_price
        else:
            # PRD §3: NO fake market data in runtime. If the live Binance
            # public ticker is unavailable, raise so callers can decide
            # to wait / log / skip — never silently substitute a constant.
            import json, urllib.request
            url = f"https://fapi.binance.com/fapi/v1/ticker/price?symbol={symbol}"
            try:
                with self._http_lock:
                    with urllib.request.urlopen(url, timeout=5) as resp:
                        row = json.loads(resp.read())
                price = Decimal(row["price"])
                self._prices[symbol] = price
            except Exception as exc:
                raise RuntimeError(
                    f"binance public ticker unavailable for {symbol}: {exc}"
                ) from exc
        return Ticker(symbol, price, datetime.now(UTC))

    def get_symbols(self) -> list[str]:
        return []

    def get_exchange_info(self, symbol: str) -> dict:
        return {"symbol": symbol, "step_size": "0.001", "tick_size": "0.01", "min_notional": "5"}

    # ── simulated execution ───────────────────────────────────────────────────

    def get_balance(self, asset: str = "USDT") -> Balance:
        if asset != self._balance.asset:
            return Balance(asset, Decimal("0"), Decimal("0"))
        return self._balance

    def get_position(self, symbol: str) -> Position | None:
        return self._positions.get(symbol)

    def place_order(self, request: OrderRequest) -> OrderResult:
        order_id = str(uuid4())

        # Conditional orders (TP/SL) are stored as NEW and triggered by update_market_price.
        # They need no fill price — resolve their stop side and return immediately.
        if request.order_type.value in {"STOP_MARKET", "TAKE_PROFIT_MARKET"}:
            result = OrderResult(
                order_id, request.symbol, "NEW", Decimal("0"), None,
                {"stopPrice": str(request.stop_price), "side": request.side.value,
                 "type": request.order_type.value},
            )
            self._orders[order_id] = result
            return result

        # PRD §3: NO fake fill prices. For actual-fill orders (MARKET/LIMIT),
        # require a price from the caller or from a prior ticker lookup.
        if request.price is not None:
            fill_price = request.price
        else:
            cached = self._prices.get(request.symbol)
            if cached is not None:
                fill_price = cached
            else:
                raise RuntimeError(
                    f"refusing to fill {request.symbol} order without a market price; "
                    "call update_market_price or pass a price on the request"
                )

        # Market order: immediate fill
        current = self._positions.get(request.symbol)
        if current and current.side != request.side:
            # Closing existing position
            pnl = (fill_price - current.entry_price) * current.quantity * Decimal(current.leverage)
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
                request.symbol, request.side, request.quantity, fill_price, fill_price,
                self._leverage, opened_at=datetime.now(UTC),
            )

        result = OrderResult(order_id, request.symbol, "FILLED", request.quantity, fill_price)
        self._orders[order_id] = result
        return result

    def update_market_price(self, symbol: str, price: Decimal) -> None:
        """Update paper price and trigger any conditional orders that have fired."""
        if price <= 0:
            raise ValueError("market price must be positive")
        self._prices[symbol] = price
        position = self._positions.get(symbol)
        if position is not None:
            pnl = (price - position.entry_price) * position.quantity * Decimal(position.leverage)
            if position.side.value == "SELL":
                pnl = -pnl
            self._positions[symbol] = Position(
                symbol=position.symbol,
                side=position.side,
                quantity=position.quantity,
                entry_price=position.entry_price,
                mark_price=price,
                leverage=position.leverage,
                unrealized_pnl=pnl,
                strategy_id=position.strategy_id,
                opened_at=position.opened_at,
            )

        for order in list(self._orders.values()):
            current = self._orders.get(order.order_id)
            if current is None or current.symbol != symbol or current.status != "NEW":
                continue
            stop_price = Decimal(current.raw["stopPrice"])
            order_type = current.raw.get("type", "")
            raw_side = current.raw["side"]
            should_fill = False
            if order_type == "STOP_MARKET":
                # STOP_MARKET: SELL fires on price drop, BUY fires on price rise
                should_fill = (raw_side == "SELL" and price <= stop_price) or (raw_side == "BUY" and price >= stop_price)
            elif order_type == "TAKE_PROFIT_MARKET":
                # TAKE_PROFIT_MARKET: SELL fires on price rise, BUY fires on price drop
                should_fill = (raw_side == "SELL" and price >= stop_price) or (raw_side == "BUY" and price <= stop_price)
            if not should_fill:
                continue

            position = self._positions.get(symbol)
            quantity = position.quantity if position else Decimal("0")
            if position:
                pnl = (price - position.entry_price) * quantity * Decimal(position.leverage)
                if position.side.value == "SELL":
                    pnl = -pnl
                self._balance = Balance(
                    self._balance.asset,
                    self._balance.wallet_balance + pnl,
                    self._balance.available_balance + pnl,
                )
                self._positions.pop(symbol)
            self._orders[order.order_id] = OrderResult(order.order_id, symbol, "FILLED", quantity, price, current.raw)
            # Cancel sibling conditional orders
            for sib in list(self._orders.values()):
                if sib.symbol == symbol and sib.order_id != order.order_id and sib.status == "NEW":
                    self.cancel_order(symbol, sib.order_id)

    def get_open_orders(self, symbol: str | None = None) -> list[OrderResult]:
        return [o for o in self._orders.values()
                if o.status not in {"FILLED", "CANCELED"} and (symbol is None or o.symbol == symbol)]

    def get_order_status(self, symbol: str, order_id: str) -> OrderResult:
        order = self._orders.get(order_id)
        if order is None or order.symbol != symbol:
            raise KeyError(f"unknown order {order_id}")
        return order

    def cancel_order(self, symbol: str, order_id: str) -> None:
        order = self.get_order_status(symbol, order_id)
        self._orders[order_id] = OrderResult(
            order.order_id, order.symbol, "CANCELED",
            order.executed_quantity, order.average_price, order.raw,
        )

    def cancel_all_orders(self, symbol: str) -> None:
        for order in list(self._orders.values()):
            if order.symbol == symbol and order.status not in {"FILLED", "CANCELED"}:
                self.cancel_order(symbol, order.order_id)

    def set_leverage(self, symbol: str, leverage: int) -> None:
        if leverage < 1:
            raise ValueError("leverage must be at least 1")

    def health_check(self) -> bool:
        return True
