"""Create the selected adapter while preserving trading safety gates."""

from .base import ExchangeAdapter
from .binance_futures import BinanceFuturesAdapter
from .paper import PaperTradingAdapter
from app.config import ExchangeProvider, Settings, TradingMode


def create_exchange(settings: Settings) -> ExchangeAdapter:
    if settings.trading_mode in (TradingMode.PAPER, TradingMode.BACKTEST):
        return PaperTradingAdapter()
    if settings.exchange_provider is ExchangeProvider.BINANCE:
        if settings.trading_mode is TradingMode.TESTNET:
            return BinanceFuturesAdapter(settings.binance_api_key, settings.binance_api_secret, testnet=True)
        if settings.trading_mode is TradingMode.LIVE:
            return BinanceFuturesAdapter(settings.binance_api_key, settings.binance_api_secret, testnet=False)
    if settings.exchange_provider is ExchangeProvider.HYPERLIQUID:
        from .hyperliquid import HyperliquidAdapter
        return HyperliquidAdapter(settings.hyperliquid_api_url, settings.hyperliquid_wallet_address)
    if settings.exchange_provider is ExchangeProvider.DEX:
        raise NotImplementedError(
            "DEX execution is not yet implemented. "
            "Use paper mode for now, or configure TRADING_MODE=dex with "
            "EXCHANGE_PROVIDER=hyperliquid for Hyperliquid DEX execution."
        )
    raise ValueError("selected exchange provider has no executable adapter yet")