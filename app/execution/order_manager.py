"""Coordinate signal admission and validated order submission."""

from decimal import Decimal

from app.exchange.base import ExchangeAdapter
from app.exchange.models import OrderRequest, OrderSide, OrderType
from app.risk import PositionSizer, RiskManager, StopLossCalculator
from app.signals.models import Signal, SignalSide

from .dex_gate import DexOrderGate
from .position_manager import PositionManager
from .reconciliation import Reconciler


class OrderManager:
    """Keep strategy decisions separate from exchange execution."""

    def __init__(self, exchange: ExchangeAdapter, risk: RiskManager, sizer: PositionSizer, reconciler: Reconciler | None = None) -> None:
        self._exchange = exchange
        self._risk = risk
        self._sizer = sizer
        self._positions = PositionManager(exchange)
        self._reconciler = reconciler
        self._dex_gate = DexOrderGate(exchange)

    def process_signal(self, signal: Signal, daily_pnl: Decimal = Decimal("0"), open_positions: int = 0, leverage: int = 1, position_notional: Decimal | None = None):
        if signal.side is SignalSide.HOLD:
            return None
        if self._reconciler and self._reconciler.trading_blocked:
            return None
        if self._positions.get(signal.symbol) is not None:
            return None
        decision = self._risk.approve(Decimal(str(signal.confidence)), daily_pnl, open_positions, leverage)
        if not decision.approved:
            return None
        ticker = self._exchange.get_ticker(signal.symbol)
        if position_notional is not None and position_notional > 0:
            # Use a fixed notional dollar amount (e.g. $10) regardless of stop distance.
            raw_quantity = (position_notional * Decimal(str(leverage))) / ticker.price
            quantity = self._sizer._quantize(raw_quantity)
            if quantity <= 0 and getattr(self._exchange, "allows_fractional_quantities", False):
                quantity = raw_quantity
        else:
            stop = StopLossCalculator().percentage(ticker.price, signal.side.value, ticker.price * Decimal("0.02"))
            quantity = self._sizer.calculate(self._exchange.get_balance().available_balance, ticker.price, stop)
        if quantity <= 0:
            return None
        side = OrderSide.BUY if signal.side is SignalSide.BUY else OrderSide.SELL
        # Pass the live ticker price so the paper adapter can fill without
        # a hidden constant fallback (PRD §3: no fake prices in runtime).
        request = OrderRequest(signal.symbol, side, OrderType.MARKET, quantity, price=ticker.price)
        if self._dex_gate.supports_preview():
            # DEX providers require an explicit wallet-approval step; the
            # signal flow prepares the request but does NOT auto-approve it.
            return self._dex_gate.submit(request)
        return self._positions.submit(request)

    def balance(self):
        return self._exchange.get_balance()

    def position(self, symbol: str):
        return self._positions.get(symbol)
