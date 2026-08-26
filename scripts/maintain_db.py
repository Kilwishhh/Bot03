"""Prune operational records while retaining financial history."""

from app.config import Settings
from app.database import TradingRepository


def main() -> None:
    settings = Settings()
    repository = TradingRepository(settings.database_path)
    try:
        print(repository.prune_operational_records(settings.retention_days))
    finally:
        repository.close()


if __name__ == "__main__":
    main()