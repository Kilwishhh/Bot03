"""Optional Binance Square publisher.

This module is **off by default**. Binance does not publish a first-party
public posting API; the endpoint configured here is a placeholder that
matches the convention used by partner-integration programs. If the
endpoint rejects requests, the publisher records the failure and
continues — it must never block or fail trading.

Safety contract (enforced here, not assumed):
  * No HTTP call is made unless ``BINANCE_SQUARE_API_KEY`` is set.
  * Posting is gated by an explicit ``enable_binance_square`` flag.
  * A daily post counter enforces a configurable limit (default 95).
  * The publisher exposes a queue so signals are not lost when the API
    is unreachable; flush is opt-in.
  * Every failure is recorded via the standard library logger — the
    caller (the trading loop) never sees an exception.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from collections import deque
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .signal_publisher import SignalPublisher, format_signal

logger = logging.getLogger(__name__)

DEFAULT_ENDPOINT = "https://www.binance.com/bapi/composite/v1/public/pgc/openApi/content/add"
DEFAULT_DAILY_LIMIT = 95
DEFAULT_REQUEST_TIMEOUT = 10.0


class BinanceSquareConfig:
    """Tiny JSON-file-backed config + post log + queue.

    Persists to ``BINANCE_SQUARE_STATE_DIR`` (default: current working
    directory). All writes are atomic — the file is written to a temp
    path and then replaced — so a crash mid-write cannot corrupt state.
    """

    def __init__(self, state_dir: str | os.PathLike[str] | None = None) -> None:
        self._dir = Path(state_dir or os.environ.get("BINANCE_SQUARE_STATE_DIR", "."))
        self._dir.mkdir(parents=True, exist_ok=True)
        self.config_path = self._dir / "square_config.json"
        self.log_path = self._dir / "post_log.json"
        self.queue_path = self._dir / "post_queue.json"
        self._lock = threading.Lock()
        self.config: dict[str, Any] = self._load_json(self.config_path, {
            "posting_enabled": False,
            "last_toggle": None,
        })
        self.logs: dict[str, Any] = self._load_json(self.log_path, {"posts": []})
        self.queue: dict[str, Any] = self._load_json(self.queue_path, {"pending": []})

    @staticmethod
    def _load_json(path: Path, default: dict[str, Any]) -> dict[str, Any]:
        try:
            with path.open("r", encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return default

    def _atomic_write(self, path: Path, data: dict[str, Any]) -> None:
        tmp = path.with_suffix(path.suffix + ".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        tmp.replace(path)

    def save_config(self) -> None:
        with self._lock:
            self._atomic_write(self.config_path, self.config)

    def save_logs(self) -> None:
        with self._lock:
            self._atomic_write(self.log_path, self.logs)

    def save_queue(self) -> None:
        with self._lock:
            self._atomic_write(self.queue_path, self.queue)

    def toggle(self, status: bool | None = None) -> bool:
        with self._lock:
            if status is None:
                self.config["posting_enabled"] = not self.config.get("posting_enabled", False)
            else:
                self.config["posting_enabled"] = bool(status)
            self.config["last_toggle"] = datetime.now(UTC).isoformat()
        self.save_config()
        return self.config["posting_enabled"]

    def is_enabled(self) -> bool:
        return bool(self.config.get("posting_enabled", False))

    def get_today_count(self) -> int:
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        with self._lock:
            return sum(1 for post in self.logs.get("posts", []) if post.get("date") == today)

    def log_post(self, message: str) -> None:
        with self._lock:
            self.logs.setdefault("posts", []).append({
                "date": datetime.now(UTC).strftime("%Y-%m-%d"),
                "time": datetime.now(UTC).isoformat(),
                "message": message[:200],
            })
        self.save_logs()


class BinanceSquarePoster(SignalPublisher):
    """Safe-by-default Binance Square publisher with a queue and daily limit.

    Implements the :class:`SignalPublisher` contract so it can be wrapped
    in a :class:`DeduplicatingPublisher` exactly like the Telegram one.
    Any failure — network, auth, JSON, rate-limit — is logged and
    swallowed: ``publish`` never raises.
    """

    def __init__(
        self,
        api_key: str | None = None,
        endpoint: str = DEFAULT_ENDPOINT,
        daily_limit: int = DEFAULT_DAILY_LIMIT,
        timeout: float = DEFAULT_REQUEST_TIMEOUT,
        state_dir: str | os.PathLike[str] | None = None,
    ) -> None:
        self._api_key = api_key or os.environ.get("BINANCE_SQUARE_API_KEY", "")
        self._endpoint = endpoint
        self._daily_limit = max(1, int(daily_limit))
        self._timeout = max(1.0, float(timeout))
        self._state = BinanceSquareConfig(state_dir=state_dir)
        self._recent_failures: deque[float] = deque(maxlen=20)

    # ---- Capability checks --------------------------------------------

    @property
    def api_available(self) -> bool:
        return bool(self._api_key)

    def is_posting_enabled(self) -> bool:
        return self._state.is_enabled()

    def can_post(self) -> bool:
        if not self.api_available:
            return False
        if not self.is_posting_enabled():
            return False
        return self._state.get_today_count() < self._daily_limit

    # ---- Queue API ----------------------------------------------------

    def enqueue(self, message: str, priority: int = 5, category: str = "general") -> None:
        """Add a post to the queue regardless of API/toggle state.

        Queued items survive process restarts because the queue is
        persisted to disk.
        """
        if not message:
            return
        with self._state._lock:
            self._state.queue.setdefault("pending", []).append({
                "message": message,
                "priority": int(priority),
                "category": category,
                "added_at": datetime.now(UTC).isoformat(),
            })
        self._state.save_queue()
        logger.info("Binance Square: queued (%s, priority=%s) %s", category, priority, message[:60])

    def queue_summary(self) -> dict[str, int]:
        with self._state._lock:
            by_cat: dict[str, int] = {}
            for post in self._state.queue.get("pending", []):
                cat = post.get("category", "general")
                by_cat[cat] = by_cat.get(cat, 0) + 1
            return {"total": len(self._state.queue.get("pending", [])), "by_category": by_cat}

    def flush_queue(self, count: int = 1, category: str | None = None) -> dict[str, int]:
        """Try to post up to ``count`` queued items.

        Returns a status dict (success/failed/remaining/queued). Never
        raises.
        """
        if not self.can_post():
            return {
                "posted": 0,
                "failed": 0,
                "remaining": self._daily_limit - self._state.get_today_count(),
                "queue_left": len(self._state.queue.get("pending", [])),
                "skipped_reason": (
                    "no_api_key" if not self.api_available
                    else "disabled" if not self.is_posting_enabled()
                    else "daily_limit"
                ),
            }
        with self._state._lock:
            pending = [
                p for p in self._state.queue.get("pending", [])
                if category is None or p.get("category") == category
            ]
        pending.sort(key=lambda p: p.get("priority", 5))
        max_posts = min(count, len(pending), self._daily_limit - self._state.get_today_count())

        success = 0
        failed = 0
        for item in pending[:max_posts]:
            if self._post_now(item["message"]):
                success += 1
                with self._state._lock:
                    self._state.queue["pending"] = [
                        p for p in self._state.queue.get("pending", []) if p is not item
                    ]
            else:
                failed += 1
            time.sleep(1)  # rate-limit courtesy
        self._state.save_queue()
        return {
            "posted": success,
            "failed": failed,
            "remaining": self._daily_limit - self._state.get_today_count(),
            "queue_left": len(self._state.queue.get("pending", [])),
        }

    # ---- SignalPublisher contract -------------------------------------

    def publish(self, signal: Any) -> None:
        """Queue a formatted signal for posting.

        The signal is enqueued (not posted immediately) so the API can
        be unreachable without losing the signal. To post synchronously,
        call :meth:`flush_queue` after publishing.
        """
        if signal is None:
            return
        message = format_signal(signal)
        side = getattr(signal, "side", None)
        side_value = getattr(side, "value", str(side)) if side else "HOLD"
        priority = 1 if side_value == "BUY" else 2 if side_value == "SELL" else 5
        self.enqueue(message, priority=priority, category="signal")

    # ---- Internals ----------------------------------------------------

    def _post_now(self, message: str) -> bool:
        """Make the HTTP call. Returns True on a 2xx response, else False."""
        if not self.can_post():
            return False
        payload = json.dumps({"content": message, "contentType": "text"}).encode("utf-8")
        request = Request(
            self._endpoint,
            data=payload,
            method="POST",
            headers={
                "X-Square-OpenAPI-Key": self._api_key,
                "Content-Type": "application/json",
            },
        )
        try:
            with urlopen(request, timeout=self._timeout) as response:
                body = response.read()
                if 200 <= response.status < 300:
                    self._state.log_post(message)
                    return True
                logger.warning("Binance Square: HTTP %s — %s", response.status, body[:200])
                self._recent_failures.append(time.time())
                return False
        except HTTPError as e:
            logger.warning("Binance Square: HTTP %s — %s", e.code, e.reason)
            self._recent_failures.append(time.time())
            return False
        except (URLError, TimeoutError, OSError) as e:
            logger.warning("Binance Square: network error — %s", e)
            self._recent_failures.append(time.time())
            return False
        except Exception as e:  # noqa: BLE001 — last line of defence, must not crash trading
            logger.warning("Binance Square: unexpected error — %s", e)
            self._recent_failures.append(time.time())
            return False

    def get_status(self) -> dict[str, Any]:
        return {
            "api_available": self.api_available,
            "posting_enabled": self.is_posting_enabled(),
            "today_count": self._state.get_today_count(),
            "daily_limit": self._daily_limit,
            "remaining": self._daily_limit - self._state.get_today_count(),
            "queued": self.queue_summary(),
            "last_toggle": self._state.config.get("last_toggle"),
            "endpoint": self._endpoint,
        }
