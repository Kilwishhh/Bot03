from decimal import Decimal
from datetime import datetime, timezone
from app.exchange.paper import PaperTradingAdapter
from app.execution import OrderManager
from app.execution import Reconciler
from app.risk import PositionSizer, RiskManager
from app.signals import Signal, SignalSide


def test_order_manager_rejects_hold_without_exchange_order():
    exchange = PaperTradingAdapter()
    manager = OrderManager(exchange, RiskManager(Decimal("30"), 3, Decimal("0.7"), 5), PositionSizer(Decimal("0.01")))
    signal = Signal("BTCUSDT", SignalSide.HOLD, 0, datetime.now(timezone.utc))
    assert manager.process_signal(signal) is None


def test_order_manager_routes_approved_signal_to_paper_adapter():
    exchange = PaperTradingAdapter(Decimal("1000"))
    manager = OrderManager(exchange, RiskManager(Decimal("30"), 3, Decimal("0.7"), 5), PositionSizer(Decimal("0.01")))
    signal = Signal("BTCUSDT", SignalSide.BUY, 0.9, datetime.now(timezone.utc))
    result = manager.process_signal(signal)
    assert result is not None
    assert result.status == "FILLED"


def test_order_manager_blocks_low_confidence_signal():
    exchange = PaperTradingAdapter()
    manager = OrderManager(exchange, RiskManager(Decimal("30"), 3, Decimal("0.7"), 5), PositionSizer(Decimal("0.01")))
    signal = Signal("BTCUSDT", SignalSide.BUY, 0.4, datetime.now(timezone.utc))
    assert manager.process_signal(signal) is None


def test_order_manager_blocks_duplicate_position():
    exchange = PaperTradingAdapter(Decimal("1000"))
    manager = OrderManager(exchange, RiskManager(Decimal("30"), 3, Decimal("0.7"), 5), PositionSizer(Decimal("0.01")))
    signal = Signal("BTCUSDT", SignalSide.BUY, 0.9, datetime.now(timezone.utc))
    assert manager.process_signal(signal) is not None
    assert manager.process_signal(signal) is None


def test_order_manager_blocks_when_reconciliation_is_locked():
    exchange = PaperTradingAdapter(Decimal("1000"))
    reconciler = Reconciler(exchange)
    reconciler.trading_blocked = True
    manager = OrderManager(
        exchange,
        RiskManager(Decimal("30"), 3, Decimal("0.7"), 5),
        PositionSizer(Decimal("0.01")),
        reconciler,
    )
    signal = Signal("BTCUSDT", SignalSide.BUY, 0.9, datetime.now(timezone.utc))
    assert manager.process_signal(signal) is None