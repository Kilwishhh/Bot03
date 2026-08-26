from decimal import Decimal
from datetime import datetime, timezone
from app.exchange.models import Candle, OrderSide, OrderType, OrderRequest
from app.exchange.precision import normalize, validate_step


def test_order_request_is_exchange_neutral():
    request = OrderRequest("BTCUSDT", OrderSide.BUY, OrderType.MARKET, Decimal("0.01"))
    assert request.symbol == "BTCUSDT"
    assert request.price is None


def test_candle_contains_ohlcv():
    now = datetime.now(timezone.utc)
    candle = Candle(now, Decimal("1"), Decimal("2"), Decimal("0.5"), Decimal("1.5"), Decimal("10"), now)
    assert candle.high > candle.low


def test_precision_rounds_down_to_exchange_step():
    assert normalize(Decimal("0.0129"), Decimal("0.001")) == Decimal("0.012")
    validate_step(Decimal("0.012"), Decimal("0.001"), "quantity")
