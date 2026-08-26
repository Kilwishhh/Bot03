from datetime import datetime, timedelta, timezone
from decimal import Decimal
from app.exchange.models import Candle
from app.market_data import MarketDataHealth
from app.signals import SignalEngine, SignalSide
from app.strategy import IndicatorStrategy


def test_signal_engine_holds_for_stale_data():
    now = datetime.now(timezone.utc)
    old = now - timedelta(minutes=20)
    candle = Candle(old, Decimal("1"), Decimal("1"), Decimal("1"), Decimal("1"), Decimal("1"), old + timedelta(minutes=1))
    signal = SignalEngine(IndicatorStrategy(), MarketDataHealth()).generate("BTCUSDT", [candle])
    assert signal.side is SignalSide.HOLD
    assert "stale" in signal.reason[0]