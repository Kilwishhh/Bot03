from decimal import Decimal

from app.exchange.paper import PaperTradingAdapter
from app.market_data import AdapterMarketDataProvider


def test_market_data_provider_uses_exchange_contract():
    provider = AdapterMarketDataProvider(PaperTradingAdapter())
    assert provider.candles("BTCUSDT", "15m") == []
    # Seed the price cache so ticker() doesn't need a network call.
    # The provider MUST use a real or seeded price — never a constant.
    provider._exchange._prices["BTCUSDT"] = Decimal("30000")
    assert provider.ticker("BTCUSDT").price == Decimal("30000")
