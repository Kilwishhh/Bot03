"""Command-line entry point for the Phase 1 bot foundation."""

import argparse
from decimal import Decimal

from .config.settings import Settings
from .monitoring.logger import configure_logging


def main() -> None:
    parser = argparse.ArgumentParser(prog="crypto-bot")
    parser.add_argument("command", choices=["status", "start", "health", "paper-demo"], nargs="?", default="status")
    parser.add_argument("--mode", choices=["paper", "testnet", "live", "backtest", "dex"])
    parser.add_argument("--cycles", type=int, default=1, help="cycles for start; use 0 to run continuously")
    parser.add_argument("--interval", type=float, default=None, help="seconds between cycles")
    args = parser.parse_args()
    settings = Settings(trading_mode=args.mode) if args.mode else Settings()
    configure_logging(settings.log_level)
    if args.command == "paper-demo":
        from scripts.run_paper_demo import main as run_paper_demo
        run_paper_demo()
    elif args.command == "status":
        print(f"mode={settings.trading_mode.value} provider={settings.exchange_provider.value} symbol={settings.default_symbol} timeframe={settings.timeframe}")
        print(f"live_trading_enabled={settings.enable_live_trading}")
    elif args.command == "health":
        from .exchange import create_exchange
        try:
            exchange = create_exchange(settings)
            print(f"healthy: configuration loaded exchange_reachable={exchange.health_check()}")
        except (ValueError, RuntimeError) as error:
            print(f"unhealthy: {error}")
    else:
        from .exchange import create_exchange
        exchange = create_exchange(settings)
        if args.cycles < 0:
            parser.error("--cycles cannot be negative")
        from .database import TradingRepository
        from .database.migration_runner import apply_migrations
        from .execution import OrderManager
        from .market_data import AdapterMarketDataProvider
        from .notifications import DeduplicatingPublisher, TelegramNotifier, TelegramSignalPublisher
        from .risk import PositionSizer, RiskManager
        from .runtime import BotRunner, TradingCycle
        from .signals import SignalEngine
        from .strategy import create_strategy
        publisher = None
        if settings.enable_telegram and settings.telegram_bot_token and settings.telegram_chat_id:
            publisher = DeduplicatingPublisher(TelegramSignalPublisher(TelegramNotifier(settings.telegram_bot_token, settings.telegram_chat_id)))
        repository = TradingRepository()
        apply_migrations(repository.db)
        cycle = TradingCycle(
            AdapterMarketDataProvider(exchange),
            SignalEngine(create_strategy(settings)),
            OrderManager(exchange, RiskManager(Decimal(str(settings.max_daily_loss)), settings.max_open_positions, Decimal(str(settings.min_signal_confidence)), settings.max_leverage, Decimal(str(settings.max_exposure)), settings.max_consecutive_losses), PositionSizer(Decimal(str(settings.risk_per_trade)))),
            repository,
            publisher,
        )
        runner = BotRunner(cycle, settings.default_symbol, settings.timeframe, args.interval or settings.poll_interval_seconds)
        completed = runner.run(None if args.cycles == 0 else args.cycles)
        print(f"bot completed cycles={completed} mode={settings.trading_mode.value} using={exchange.__class__.__name__}")


if __name__ == "__main__":
    main()
