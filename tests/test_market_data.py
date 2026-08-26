from decimal import Decimal
from app.exchange.paper import PaperTradingAdapter
from app.market_data import AdapterMarketDataProvider


def test_market_data_provider_uses_exchange_contract():
    provider = AdapterMarketDataProvider(PaperTradingAdapter())
    assert provider.candles("BTCUSDT", "15m") == []
    assert provider.ticker("BTCUSDT").price == Decimal("100")