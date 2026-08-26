from decimal import Decimal
from app.exchange.models import OrderRequest, OrderSide, OrderType
from app.exchange.paper import PaperTradingAdapter


def test_paper_order_does_not_need_network():
    adapter = PaperTradingAdapter(Decimal("1000"))
    result = adapter.place_order(OrderRequest("BTCUSDT", OrderSide.BUY, OrderType.MARKET, Decimal("0.01")))
    assert result.status == "FILLED"
    assert adapter.health_check() is True


def test_paper_opposite_order_closes_position_and_updates_balance():
    adapter = PaperTradingAdapter(Decimal("1000"))
    adapter.place_order(OrderRequest("BTCUSDT", OrderSide.BUY, OrderType.MARKET, Decimal("1"), Decimal("100")))
    adapter.place_order(OrderRequest("BTCUSDT", OrderSide.SELL, OrderType.MARKET, Decimal("1"), Decimal("110")))
    assert adapter.get_position("BTCUSDT") is None
    assert adapter.get_balance().wallet_balance == Decimal("1010")
