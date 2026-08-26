from decimal import Decimal
import pytest
from app.exchange.models import OrderRequest, OrderSide, OrderType
from app.exchange.paper import PaperTradingAdapter


def test_paper_order_status_and_cancel_all_are_available():
    exchange = PaperTradingAdapter()
    result = exchange.place_order(OrderRequest("BTCUSDT", OrderSide.BUY, OrderType.MARKET, Decimal("1")))
    assert exchange.get_order_status("BTCUSDT", result.order_id).status == "FILLED"
    assert exchange.get_open_orders("BTCUSDT") == []
    exchange.set_leverage("BTCUSDT", 2)


def test_paper_rejects_invalid_leverage():
    with pytest.raises(ValueError):
        PaperTradingAdapter().set_leverage("BTCUSDT", 0)