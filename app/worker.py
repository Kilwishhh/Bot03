"""Persistent paper/testnet worker controlled through SQLite state."""

import time
from decimal import Decimal

from app.config import Settings
from app.database import TradingRepository
from app.database.migration_runner import apply_migrations
from app.exchange import create_exchange
from app.execution import OrderManager
from app.market_data import AdapterMarketDataProvider
from app.notifications import DeduplicatingPublisher, TelegramNotifier, TelegramSignalPublisher
from app.risk import PositionSizer, RiskManager
from app.runtime import BotRunner, TradingCycle
from app.signals import SignalEngine
from app.strategy import create_strategy


def build_runner(settings: Settings, repository: TradingRepository) -> BotRunner:
    exchange = create_exchange(settings)
    publisher = None
    if settings.enable_telegram and settings.telegram_bot_token and settings.telegram_chat_id:
        publisher = DeduplicatingPublisher(TelegramSignalPublisher(TelegramNotifier(settings.telegram_bot_token, settings.telegram_chat_id)))
    cycle = TradingCycle(
        AdapterMarketDataProvider(exchange),
        SignalEngine(create_strategy(settings)),
        OrderManager(
            exchange,
            RiskManager(Decimal(str(settings.max_daily_loss)), settings.max_open_positions, Decimal(str(settings.min_signal_confidence)), settings.max_leverage, Decimal(str(settings.max_exposure)), settings.max_consecutive_losses, Decimal(str(settings.max_drawdown_pct))),
            PositionSizer(Decimal(str(settings.risk_per_trade))),
        ),
        repository,
        publisher,
    )
    return BotRunner(cycle, settings.default_symbol, settings.timeframe, settings.poll_interval_seconds)


def main() -> None:
    settings = Settings()
    repository = TradingRepository(settings.database_path)
    apply_migrations(repository.db)
    runner = None
    try:
        while True:
            state = repository.control_state()
            desired = state[0] if state else "stopped"
            if desired == "running" and runner is None:
                runner = build_runner(settings, repository)
            if desired in {"stopping", "stopped"} and runner is not None:
                runner.stop()
                runner = None
                repository.set_control_state("stopped")
            if runner is not None:
                repository.set_control_state("running", heartbeat_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
                runner.run(max_cycles=1)
            time.sleep(1)
    finally:
        repository.close()


if __name__ == "__main__":
    main()
