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
        # Dedupe window: records with same (logger, level, msg) within this
        # many seconds collapse into one entry. Prevents duplicate entries when
        # a logger AND its parent (e.g. app.* + root) both carry this handler.
        self._dedupe_window_s = 0.5

    def emit(self, record: logging.LogRecord) -> None:
        # Drop all uvicorn logs — they duplicate uvicorn's own logging.
        # Both 'uvicorn.access' and 'uvicorn.error' propagate to the root logger,
        # so we must block both here to prevent duplicate entries.
        if record.name in ("uvicorn.access", "uvicorn.error"):
            return
        msg = record.getMessage()
        ts = record.created
        with self._lock:
            # If a sibling logger (parent) just captured the same record, skip.
            for prev in reversed(self._records[-5:]):
                if (ts - float(prev["_ts"])) > self._dedupe_window_s:
                    break
                if prev["logger"] == record.name and prev["level"] == record.levelname and prev["msg"] == msg:
                    return
            self._records.append({
                "_ts": ts,
                "ts": datetime.fromtimestamp(ts, tz=UTC).isoformat(timespec="milliseconds"),
                "level": record.levelname,
                "logger": record.name,
                "msg": msg,
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
