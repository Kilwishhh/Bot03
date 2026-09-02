from decimal import Decimal

from app.exchange.paper import PaperTradingAdapter
from app.market_data import AdapterMarketDataProvider


def test_market_data_provider_uses_exchange_contract():
    provider = AdapterMarketDataProvider(PaperTradingAdapter())
    # PaperTradingAdapter fetches real Binance Futures candles; assert non-empty.
    candles = provider.candles("BTCUSDT", "15m")
    assert len(candles) > 0, f"expected real candles from Binance, got {len(candles)}"
    # Seed the price cache so ticker() doesn't need a network call.
    provider._exchange._prices["BTCUSDT"] = Decimal("30000")
    assert provider.ticker("BTCUSDT").price == Decimal("30000")
