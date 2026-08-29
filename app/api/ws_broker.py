"""WebSocket subscribers for real-time event broadcasting."""
import asyncio
import json
from typing import Any


class EventBroker:
    """Fan-out broker for bot events. Connected clients receive a copy of
    every event published. Thread-safe enqueue; clients are drained by the
    websocket task on its own event loop.
    """

    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue] = set()
        self._loop: asyncio.AbstractEventLoop | None = None

    def attach(self, queue: asyncio.Queue) -> None:
        self._subscribers.add(queue)

    def detach(self, queue: asyncio.Queue) -> None:
        self._subscribers.discard(queue)

    async def publish(self, event: dict[str, Any]) -> None:
        # Snapshot subscribers to avoid mutation during iteration
        for q in list(self._subscribers):
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:  # pragma: no cover - bounded queue
                pass

    def publish_threadsafe(self, event: dict[str, Any]) -> None:
        """Called from non-async contexts (background bot thread) to push
        an event onto every subscriber queue. Silently no-op if no loop is
        attached (e.g. during shutdown)."""
        if self._loop is None:
            return
        try:
            self._loop.call_soon_threadsafe(self._schedule, event)
        except RuntimeError:
            pass

    def _schedule(self, event: dict[str, Any]) -> None:
        for q in list(self._subscribers):
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:  # pragma: no cover
                pass


broker = EventBroker()


def publish_event(event_type: str, message: str = "", **extra: Any) -> None:
    """Convenience helper for background threads to publish an event."""
    payload: dict[str, Any] = {
        "type": event_type,
        "message": message,
    }
    payload.update(extra)
    broker.publish_threadsafe(payload)


def set_loop(loop: asyncio.AbstractEventLoop) -> None:
    broker._loop = loop  # noqa: SLF001 - broker lifecycle owned by server


def encode(event: dict[str, Any]) -> str:
    return json.dumps(event, default=str)
