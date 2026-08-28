"""Market-data freshness checks used before strategy execution."""

from datetime import UTC, datetime, timedelta

from app.exchange.models import Candle


class MarketDataHealth:
    def __init__(self, max_age: timedelta = timedelta(minutes=5)) -> None:
        self.max_age = max_age

    def is_fresh(self, candles: list[Candle], now: datetime | None = None) -> bool:
        if not candles:
            return False
        current_time = now or datetime.now(UTC)
        latest = candles[-1].close_time
        if latest.tzinfo is None:
            latest = latest.replace(tzinfo=UTC)
        return current_time - latest <= self.max_age

    def has_valid_sequence(self, candles: list[Candle]) -> bool:
        # Binance REST API returns candles in ascending order and without duplicates;
        # allow descending (current incomplete candle appended) but reject true duplicates.
        if not candles:
            return False
        seen_times: set[int] = set()
        for c in candles:
            t = int(c.open_time.timestamp())
            if t in seen_times:
                return False
            seen_times.add(t)
        return True
