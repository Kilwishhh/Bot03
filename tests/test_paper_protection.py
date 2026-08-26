from decimal import Decimal
from app.exchange.models import OrderRequest, OrderSide, OrderType
from app.exchange.paper import PaperTradingAdapter


def test_paper_conditional_order_waits_for_trigger():
    exchange = PaperTradingAdapter(Decimal("1000"))
    exchange.place_order(OrderRequest("BTCUSDT", OrderSide.BUY, OrderType.MARKET, Decimal("1"), Decimal("100")))
    stop = exchange.place_order(OrderRequest("BTCUSDT", OrderSide.SELL, OrderType.STOP_MARKET, Decimal("1"), stop_price=Decimal("98")))
    assert stop.status == "NEW"
    exchange.update_market_price("BTCUSDT", Decimal("98"))
    assert exchange.get_ticker("BTCUSDT").price == Decimal("98")
    assert exchange.get_order_status("BTCUSDT", stop.order_id).status == "FILLED"
    assert exchange.get_position("BTCUSDT") is None
    assert exchange.get_balance().wallet_balance == Decimal("998")


def test_triggered_protection_cancels_sibling_order():
    exchange = PaperTradingAdapter(Decimal("1000"))
    exchange.place_order(OrderRequest("BTCUSDT", OrderSide.BUY, OrderType.MARKET, Decimal("1"), Decimal("100")))
    stop = exchange.place_order(OrderRequest("BTCUSDT", OrderSide.SELL, OrderType.STOP_MARKET, Decimal("1"), stop_price=Decimal("98")))
    target = exchange.place_order(OrderRequest("BTCUSDT", OrderSide.SELL, OrderType.TAKE_PROFIT_MARKET, Decimal("1"), stop_price=Decimal("104")))
    exchange.update_market_price("BTCUSDT", Decimal("98"))
    assert exchange.get_order_status("BTCUSDT", stop.order_id).status == "FILLED"
    assert exchange.get_order_status("BTCUSDT", target.order_id).status == "CANCELED"