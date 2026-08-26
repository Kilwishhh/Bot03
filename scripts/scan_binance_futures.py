"""Scan Binance Futures public market data without placing orders."""

import argparse
from app.config import Settings
from app.exchange.binance_futures import BinanceFuturesAdapter
from app.market_data import AdapterMarketDataProvider, FuturesSignalScanner
from app.notifications import DeduplicatingPublisher, TelegramNotifier, TelegramSignalPublisher
from app.signals import SignalEngine
from app.strategy import IndicatorStrategy


def main() -> None:
    parser = argparse.ArgumentParser(description="Scan Binance Futures public market data")
    parser.add_argument("--timeframe", default=None)
    parser.add_argument("--limit", type=int, default=100, help="candles per symbol")
    parser.add_argument("--max-symbols", type=int, default=None, help="optional cap for testing")
    args = parser.parse_args()
    # Public scanning is read-only and must not require private trading credentials.
    settings = Settings(trading_mode="paper")
    exchange = BinanceFuturesAdapter("", "", testnet=False)
    publisher = None
    if settings.enable_telegram and settings.telegram_bot_token and settings.telegram_chat_id:
        publisher = DeduplicatingPublisher(TelegramSignalPublisher(TelegramNotifier(settings.telegram_bot_token, settings.telegram_chat_id)))
    scanner = FuturesSignalScanner(
        exchange,
        AdapterMarketDataProvider(exchange),
        SignalEngine(IndicatorStrategy()),
        publisher,
    )
    symbols = exchange.get_symbols()
    if args.max_symbols is not None:
        symbols = symbols[:args.max_symbols]
    signals = scanner.scan(args.timeframe or settings.timeframe, limit=args.limit, symbols=symbols)
    actionable = [signal for signal in signals if signal.side.value != "HOLD"]
    print(f"scanned_symbols={len(signals)} actionable_signals={len(actionable)}")
    for signal in actionable:
        print(f"{signal.symbol} {signal.side.value} confidence={signal.confidence:.2f}")


if __name__ == "__main__":
    main()