"""Run offline checks for the application without credentials or network."""

from app.config import Settings
from app.database import TradingRepository
from app.exchange.paper import PaperTradingAdapter


def main() -> None:
    settings = Settings(_env_file=None)
    exchange = PaperTradingAdapter()
    if not exchange.health_check():
        raise SystemExit("paper exchange health check failed")
    print(f"configuration_ok=True mode={settings.trading_mode.value}")
    print("paper_adapter_ok=True")
    repository = TradingRepository(settings.database_path)
    try:
        print(f"retention_ready=True retention_days={settings.retention_days}")
    finally:
        repository.close()
    print("offline_checks_ok=True")
    print("next=run 'py -m app.main paper-demo' for a simulated order")


if __name__ == "__main__":
    main()
