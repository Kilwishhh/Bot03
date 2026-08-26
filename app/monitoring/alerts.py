"""Best-effort operational alerts with in-memory cooldowns."""

import time
from app.notifications import Notifier


class OperationalAlertManager:
    def __init__(self, notifier: Notifier | None, failure_threshold: int = 3, cooldown_seconds: int = 900) -> None:
        self._notifier = notifier
        self._failure_threshold = failure_threshold
        self._cooldown_seconds = cooldown_seconds
        self._failures = 0
        self._last_sent: dict[str, float] = {}

    def _send(self, key: str, message: str) -> None:
        if self._notifier is None:
            return
        now = time.monotonic()
        if now - self._last_sent.get(key, 0) < self._cooldown_seconds:
            return
        try:
            self._notifier.send(message)
            self._last_sent[key] = now
        except Exception:
            return

    def record_cycle_failure(self, error: Exception) -> None:
        self._failures += 1
        if self._failures >= self._failure_threshold:
            self._send("cycle_failure", f"Trading cycle failure threshold reached: {error}")

    def record_cycle_success(self) -> None:
        if self._failures >= self._failure_threshold:
            self._send("cycle_recovered", "Trading cycle recovered")
        self._failures = 0

    def record_stale_market_data(self, symbol: str) -> None:
        self._send("stale_market_data", f"Stale or missing market data: {symbol}")