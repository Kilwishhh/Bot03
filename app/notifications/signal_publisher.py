"""Publish signals without coupling publication to trade execution."""

import contextlib
from abc import ABC, abstractmethod
from datetime import UTC, datetime, timedelta

from app.signals.models import Signal


class SignalPublisher(ABC):
    @abstractmethod
    def publish(self, signal: Signal) -> None: ...


def format_signal(signal: Signal | dict) -> str:
    """Build the canonical message used by publishers and UI previews."""
    def value(name: str, default=None):
        if isinstance(signal, dict):
            return signal.get(name, default)
        return getattr(signal, name, default)

    side = value("side", "HOLD")
    side = side.value if hasattr(side, "value") else str(side)
    symbol = value("symbol", "")
    entry = value("entry_price", value("entry"))
    tp = value("tp1", value("take_profit"))
    sl = value("stop_loss")
    hits = value("confidence_hits")
    total = value("confidence_total")
    confidence = f"{hits}/{total}" if hits is not None and total else f"{float(value('confidence', 0)):.0%}"
    strategy = value("strategy_name", value("strategy", "unknown"))
    timeframe = value("timeframe", "—")
    mode = str(value("mode", "paper")).upper()
    return (
        f"{symbol} {side}\n"
        f"Entry: {entry if entry is not None else 'TBD'}\n"
        f"TP: {tp if tp is not None else '—'}\n"
        f"SL: {sl if sl is not None else '—'}\n"
        f"Confidence: {confidence}\n"
        f"Strategy: {strategy}\n"
        f"Timeframe: {timeframe}\n"
        f"Mode: {mode}"
    )


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
        now = datetime.now(UTC)
        previous = self._last_published.get(key)
        if previous is not None and now - previous < self._cooldown:
            return
        self._publisher.publish(signal)
        self._last_published[key] = now


class CompositePublisher(SignalPublisher):
    """Fan a single signal out to multiple underlying publishers.

    Every publisher receives the signal, and a failure in one does not
    stop the others. This is the safe way to chain Telegram + Binance
    Square behind a single :class:`DeduplicatingPublisher`.
    """

    def __init__(self, publishers) -> None:
        self._publishers = list(publishers)

    def publish(self, signal: Signal) -> None:
        for publisher in self._publishers:
            try:
                publisher.publish(signal)
            except Exception as exc:  # noqa: BLE001 — publisher isolation
                import logging
                logging.getLogger(__name__).warning(
                    "publisher %s failed: %s", publisher.__class__.__name__, exc
                )


class FlushingPublisher(SignalPublisher):
    """Adapter that calls ``flush()`` on a flushing-capable publisher.

    The Binance Square poster enqueues signals on :meth:`publish` (so
    they survive a missing API key) and exposes a :meth:`flush_queue`
    method that actually posts. This adapter invokes ``flush_queue`` after
    every successful publish so signals reach the API without a separate
    background worker. On any failure the signal stays in the queue and
    will be retried on the next publish.
    """

    def __init__(self, inner, count: int = 1) -> None:
        self._inner = inner
        self._count = count

    def publish(self, signal: Signal) -> None:
        self._inner.publish(signal)
        flush = getattr(self._inner, "flush_queue", None)
        if callable(flush):
            with contextlib.suppress(Exception):  # best-effort flush
                flush(self._count)


class BinanceSquarePublisher(SignalPublisher):
    """Placeholder until an official, supported Square publishing API is configured."""

    def publish(self, signal: Signal) -> None:
        raise NotImplementedError("Binance Square publishing requires an official publishing API")
