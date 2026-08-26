"""Check Binance Futures connectivity without placing an order."""

from app.config import Settings, TradingMode
from app.exchange.binance_futures import BinanceFuturesAdapter


def main() -> None:
    settings = Settings(trading_mode=TradingMode.TESTNET)
    if not settings.binance_api_key or not settings.binance_api_secret:
        raise SystemExit("Set BINANCE_API_KEY and BINANCE_API_SECRET in .env first")
    adapter = BinanceFuturesAdapter(settings.binance_api_key, settings.binance_api_secret, testnet=True)
    print(f"connected={adapter.health_check()}")
    print(adapter.get_balance())


if __name__ == "__main__":
    main()
