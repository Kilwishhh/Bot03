"""Publish signals without coupling publication to trade execution."""

from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from app.signals.models import Signal


class SignalPublisher(ABC):
    @abstractmethod
    def publish(self, signal: Signal) -> None: ...


def format_signal(signal: Signal) -> str:
    reasons = "; ".join(signal.reason) or "no reason provided"
    return f"{signal.symbol} {signal.side.value} confidence={signal.confidence:.2f}\n{reasons}"


class TelegramSignalPublisher(SignalPublisher):
    def __init__(self, notifier) -> None:
        self._notifier = notifier

    def publish(self, signal: Signal) -> None:
        self._notifier.send(format_signal(signal))


class DeduplicatingPublisher(SignalPublisher):
    """Suppress identical signal posts during a configurable cooldown."""

    def __init__(self, publisher: SignalPublisher, cooldown: timedelta = timedelta(minutes=15)) -> None:
        self._publisher = publisher
        self._cooldown = cooldown
        self._last_published: dict[tuple[str, str], datetime] = {}

    def publish(self, signal: Signal) -> None:
        key = (signal.symbol, signal.side.value)
        now = datetime.now(timezone.utc)
        previous = self._last_published.get(key)
        if previous is not None and now - previous < self._cooldown:
            return
        self._publisher.publish(signal)
        self._last_published[key] = now


class BinanceSquarePublisher(SignalPublisher):
    """Placeholder until an official, supported Square publishing API is configured."""

    def publish(self, signal: Signal) -> None:
        raise NotImplementedError("Binance Square publishing requires an official publishing API")