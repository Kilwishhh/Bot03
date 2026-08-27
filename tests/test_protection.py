from decimal import Decimal

from app.exchange.models import OrderSide, Position
from app.exchange.paper import PaperTradingAdapter
from app.execution import ProtectionManager


def test_protection_creates_stop_and_target():
    exchange = PaperTradingAdapter()
    position = Position("BTCUSDT", OrderSide.BUY, Decimal("1"), Decimal("100"), Decimal("100"), 1)
    stop, target = ProtectionManager(exchange).protect(position, Decimal("98"), Decimal("104"))
    assert stop.status == "NEW"
    assert target.status == "NEW"
