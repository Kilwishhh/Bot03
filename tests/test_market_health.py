from datetime import datetime, timedelta, timezone
from decimal import Decimal
from app.exchange.models import Candle
from app.market_data import MarketDataHealth


def test_market_data_rejects_stale_candles():
    now = datetime.now(timezone.utc)
    candle = Candle(now - timedelta(minutes=10), Decimal("1"), Decimal("1"), Decimal("1"), Decimal("1"), Decimal("1"), now - timedelta(minutes=9))
    assert MarketDataHealth().is_fresh([candle], now) is False


def test_market_data_accepts_ordered_fresh_candles():
    now = datetime.now(timezone.utc)
    candles = [Candle(now - timedelta(minutes=2), Decimal("1"), Decimal("1"), Decimal("1"), Decimal("1"), Decimal("1"), now - timedelta(minutes=1)), Candle(now - timedelta(minutes=1), Decimal("1"), Decimal("1"), Decimal("1"), Decimal("1"), Decimal("1"), now)]
    health = MarketDataHealth()
    assert health.is_fresh(candles, now) is True
    assert health.has_valid_sequence(candles) is True


def test_market_data_rejects_duplicate_timestamps():
    now = datetime.now(timezone.utc)
    candle = Candle(now, Decimal("1"), Decimal("1"), Decimal("1"), Decimal("1"), Decimal("1"), now)
    assert MarketDataHealth().has_valid_sequence([candle, candle]) is False