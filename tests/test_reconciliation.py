from decimal import Decimal

from app.exchange.models import OrderRequest, OrderSide, OrderType
from app.exchange.paper import PaperTradingAdapter
from app.execution import Reconciler


def test_reconciler_accepts_matching_empty_state():
    assert Reconciler(PaperTradingAdapter()).compare_position(None, "BTCUSDT").synchronized is True


def test_reconciler_blocks_after_position_mismatch():
    exchange = PaperTradingAdapter()
    exchange._prices["BTCUSDT"] = Decimal("30000")
    exchange.place_order(OrderRequest("BTCUSDT", OrderSide.BUY, OrderType.MARKET, Decimal("1")))
    reconciler = Reconciler(exchange)
    result = reconciler.compare_position(None, "BTCUSDT")
    assert result.synchronized is False
    assert reconciler.trading_blocked is True
