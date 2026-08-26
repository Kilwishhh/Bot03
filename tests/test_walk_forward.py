from datetime import datetime, timedelta, timezone
from decimal import Decimal
from app.backtesting import split_candles
from app.exchange.models import Candle


def test_walk_forward_split_preserves_chronological_order():
    start = datetime.now(timezone.utc)
    candles = [Candle(start + timedelta(minutes=i), Decimal(i), Decimal(i), Decimal(i), Decimal(i), Decimal("1"), start + timedelta(minutes=i + 1)) for i in range(10)]
    split = split_candles(candles)
    assert len(split.train) == 6
    assert len(split.validation) == 2
    assert len(split.test) == 2
    assert split.train[-1].close < split.validation[0].close < split.test[0].close