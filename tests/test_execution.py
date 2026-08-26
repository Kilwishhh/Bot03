from decimal import Decimal
import pytest
from app.exchange.models import OrderRequest, OrderSide, OrderType
from app.exchange.paper import PaperTradingAdapter
from app.execution import OrderValidationError, PositionManager, validate_order


def test_market_order_requires_positive_quantity():
    request = OrderRequest("BTCUSDT", OrderSide.BUY, OrderType.MARKET, Decimal("0"))
    with pytest.raises(OrderValidationError):
        validate_order(request)


def test_limit_order_requires_price():
    request = OrderRequest("BTCUSDT", OrderSide.BUY, OrderType.LIMIT, Decimal("0.01"))
    with pytest.raises(OrderValidationError):
        validate_order(request)


def test_position_manager_validates_before_submission():
    manager = PositionManager(PaperTradingAdapter())
    result = manager.submit(OrderRequest("BTCUSDT", OrderSide.BUY, OrderType.MARKET, Decimal("0.01")))
    assert result.status == "FILLED"