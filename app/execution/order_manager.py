"""Coordinate signal admission and validated order submission."""

from decimal import Decimal
from app.exchange.base import ExchangeAdapter
from app.exchange.models import OrderRequest, OrderSide, OrderType
from app.risk import PositionSizer, RiskManager, StopLossCalculator
from app.signals.models import Signal, SignalSide
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

    def process_signal(self, signal: Signal, daily_pnl: Decimal = Decimal("0"), open_positions: int = 0, leverage: int = 1):
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
        stop = StopLossCalculator().percentage(ticker.price, signal.side.value, ticker.price * Decimal("0.02"))
        quantity = self._sizer.calculate(self._exchange.get_balance().available_balance, ticker.price, stop)
        if quantity <= 0:
            return None
        side = OrderSide.BUY if signal.side is SignalSide.BUY else OrderSide.SELL
        return self._positions.submit(OrderRequest(signal.symbol, side, OrderType.MARKET, quantity))

    def balance(self):
        return self._exchange.get_balance()

    def position(self, symbol: str):
        return self._positions.get(symbol)