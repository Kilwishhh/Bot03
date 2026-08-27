"""In-memory candle cache with duplicate and ordering protection."""

from app.exchange.models import Candle


class CandleStore:
    def __init__(self, max_candles: int = 1000) -> None:
        if max_candles < 1:
            raise ValueError("max_candles must be positive")
        self.max_candles = max_candles
        self._candles: dict[str, dict[object, Candle]] = {}

    def update(self, symbol: str, candles: list[Candle]) -> list[Candle]:
        stored = self._candles.setdefault(symbol, {})
        for candle in candles:
            stored[candle.open_time] = candle
        ordered = sorted(stored.values(), key=lambda candle: candle.open_time)[-self.max_candles:]
        self._candles[symbol] = {candle.open_time: candle for candle in ordered}
        return ordered

    def get(self, symbol: str) -> list[Candle]:
        return sorted(self._candles.get(symbol, {}).values(), key=lambda candle: candle.open_time)
