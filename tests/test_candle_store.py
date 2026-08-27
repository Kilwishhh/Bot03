from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.exchange.models import Candle
from app.market_data import CandleStore


def test_candle_store_deduplicates_and_orders_candles():
    start = datetime.now(UTC)
    def candle(index, close):
        timestamp = start + timedelta(minutes=index)
        return Candle(timestamp, Decimal("1"), Decimal("1"), Decimal("1"), Decimal(close), Decimal("1"), timestamp + timedelta(minutes=1))
    store = CandleStore(2)
    result = store.update("BTCUSDT", [candle(2, "2"), candle(1, "1"), candle(2, "3")])
    assert len(result) == 2
    assert result[-1].close == Decimal("3")
