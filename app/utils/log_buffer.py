"""In-memory ring buffer for the admin Logs tab.

Attaches to both the uvicorn logger (HTTP/WebSocket traffic) and the
root logger (application-level logs) so everything shows in the UI.
"""

import logging
from datetime import datetime, UTC
from threading import Lock

MAX_ENTRIES = 2000


class _LogBuffer(logging.Handler):
    """Logging handler that stores last MAX_ENTRIES records in a deque."""

    def __init__(self) -> None:
        super().__init__()
        self._records: list[dict] = []
        self._lock = Lock()

    def emit(self, record: logging.LogRecord) -> None:
        # Drop DEBUG noise from uvicorn.access
        if record.name == "uvicorn.access" and record.levelno < logging.INFO:
            return
        with self._lock:
            self._records.append({
                "ts": datetime.fromtimestamp(record.created, tz=UTC).isoformat(timespec="milliseconds"),
                "level": record.levelname,
                "logger": record.name,
                "msg": record.getMessage(),
            })
            if len(self._records) > MAX_ENTRIES:
                self._records = self._records[-MAX_ENTRIES:]

    def tail(self, n: int = 100, since: str | None = None) -> list[dict]:
        with self._lock:
            records = self._records
            if since:
                records = [r for r in records if r["ts"] > since]
            return records[-n:]


# Module-level singleton
_buffer = _LogBuffer()


def install() -> _LogBuffer:
    """Attach the ring buffer to uvicorn and root loggers. Idempotent."""
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access", "app", ""):
        logger = logging.getLogger(name)
        if _buffer not in logger.handlers:
            logger.addHandler(_buffer)
            logger.setLevel(logging.DEBUG)
    return _buffer


def tail(n: int = 100, since: str | None = None) -> list[dict]:
    return _buffer.tail(n=n, since=since)
