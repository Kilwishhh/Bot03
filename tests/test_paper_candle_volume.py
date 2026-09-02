"""Regression test: PaperTradingAdapter.get_candles must return candles with volume.

Root cause: Candle() requires a 'volume' field. Binance klines row index 5 is volume.
Missing it caused TypeError which was silently swallowed → [] for ALL symbols.
Fix: add volume=Decimal(row[5]) to the Candle constructor in paper.py.
"""
from decimal import Decimal

from app.exchange.paper import PaperTradingAdapter
from app.market_data import AdapterMarketDataProvider


def test_paper_adapter_returns_candles_with_volume():
    """Regression: Candle(row) must include volume at index 5 or TypeError is raised."""
    adapter = PaperTradingAdapter()
    provider = AdapterMarketDataProvider(adapter)

    # BTCUSDT is always liquid — should return candles
    candles = provider.candles("BTCUSDT", "1m", limit=5)
    assert len(candles) > 0, "PaperTradingAdapter should return real Binance candles, not []"
    for c in candles:
        assert c.volume is not None, "candle volume must not be None"
        assert c.volume >= 0, "candle volume must be non-negative"


def test_paper_adapter_returns_candles_for_futures_symbols():
    """Regression: SOLUSDT, SOLVUSDT, SOMIUSDT are futures-only symbols.

    Before fix: all returned [] due to TypeError.
    After fix: should return real Binance candles.
    """
    adapter = PaperTradingAdapter()
    provider = AdapterMarketDataProvider(adapter)

    for symbol in ["SOLUSDT", "SOLVUSDT", "SOMIUSDT"]:
        candles = provider.candles(symbol, "1m", limit=5)
        assert len(candles) > 0, f"{symbol}: expected candles from Binance, got []"
        # Volume may be 0 for new/illiquid pairs (SOLVUSDT etc.); just assert field exists.
        assert candles[0].volume is not None, f"{symbol}: volume field missing"
