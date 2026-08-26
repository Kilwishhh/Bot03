from decimal import Decimal
from app.exchange.models import OrderSide, Position
from app.portfolio import PnlCalculator


def test_realized_long_pnl_is_fee_aware():
    summary = PnlCalculator().realized(OrderSide.BUY, Decimal("100"), Decimal("110"), Decimal("2"), Decimal("1"))
    assert summary.gross == Decimal("20")
    assert summary.net == Decimal("19")


def test_unrealized_short_pnl():
    position = Position("BTCUSDT", OrderSide.SELL, Decimal("2"), Decimal("100"), Decimal("90"), 1)
    assert PnlCalculator().unrealized(position).gross == Decimal("20")