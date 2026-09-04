"""Publishing service: Telegram + Binance Square, 3-way limit behavior, dedup."""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import uuid
from datetime import UTC, datetime
from typing import Any

from app.core.audit import record
from app.core.crypto import decrypt, encrypt
from app.core.rbac import AccessContext

logger = logging.getLogger(__name__)


class PublishingService:
    """Manages publishing configs + the Square daily-limit queue.

    3-way square_limit_behavior when the daily limit is reached:
      - stop_square: halt Square publishing, continue Telegram
      - telegram_only: queue Square posts, continue Telegram
      - queue: queue Square posts, publish Telegram immediately
    """

    def __init__(self, db_path: str = "trading.db") -> None:
        self._db_path = db_path
        self._lock = threading.RLock()
        self._square_today: dict[str, int] = {}  # user_id → count today

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(self._db_path, check_same_thread=False, isolation_level=None)

    # ------------------------------------------------------------------
    # Config
    # ------------------------------------------------------------------

    def get_config(self, ctx: AccessContext) -> dict[str, Any]:
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT * FROM publishing_configs WHERE user_id = ?", (ctx.user.id,)).fetchone()
            if not row:
                return {
                    "telegram_enabled": False, "telegram_chat_id": None,
                    "square_enabled": False, "square_daily_limit": 95,
                    "square_limit_behavior": "queue",
                }
            return {
                "telegram_enabled": bool(row[3]),
                "telegram_chat_id": row[2],
                "square_enabled": bool(row[9]),
                "square_daily_limit": row[6],
                "square_limit_behavior": row[7],
            }
        finally:
            conn.close()

    def update_config(self, payload: dict[str, Any], ctx: AccessContext) -> dict[str, Any]:
        conn = self._conn()
        try:
            with self._lock:
                conn.execute(
                    "INSERT OR REPLACE INTO publishing_configs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        ctx.user.id,
                        encrypt(payload.get("telegram_token", "")) if payload.get("telegram_token") else None,
                        payload.get("telegram_chat_id"),
                        1 if payload.get("telegram_enabled") else 0,
                        encrypt(payload.get("square_api_key", "")) if payload.get("square_api_key") else None,
                        payload.get("square_endpoint"),
                        payload.get("square_daily_limit", 95),
                        payload.get("square_limit_behavior", "queue"),
                        1 if payload.get("square_enabled") else 0,
                        datetime.now(UTC).isoformat(),
                    ),
                )
            record(actor=ctx.user, action="publishing.config_update", target_type="publishing_config")
            return self.get_config(ctx)
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Publishing
    # ------------------------------------------------------------------

    def publish_telegram(self, signal_id: str | None, ctx: AccessContext,
                        template: str = "default") -> dict:
        config = self.get_config(ctx)
        if not config.get("telegram_enabled"):
            return {"sent": False, "reason": "telegram not enabled"}

        conn = self._conn()
        try:
            pub_id = str(uuid.uuid4())
            token = ""
            if config.get("telegram_chat_id"):
                # decrypt token if stored
                row = conn.execute(
                    "SELECT telegram_token_enc FROM publishing_configs WHERE user_id = ?",
                    (ctx.user.id,)).fetchone()
                if row and row[0]:
                    token = decrypt(row[0])

            # Build message
            message = self._build_message(signal_id, ctx, template)
            if token and config["telegram_chat_id"]:
                try:
                    import urllib.request
                    url = f"https://api.telegram.org/bot{token}/sendMessage"
                    data = json.dumps({"chat_id": config["telegram_chat_id"], "text": message}).encode()
                    req = urllib.request.Request(url, data=data,
                        headers={"Content-Type": "application/json"})
                    with urllib.request.urlopen(req, timeout=10) as resp:
                        ok = resp.status == 200
                except Exception as exc:
                    logger.warning("Telegram publish failed: %s", exc)
                    ok = False
            else:
                ok = False

            status = "sent" if ok else "failed"
            with self._lock:
                conn.execute(
                    "INSERT INTO publications VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (pub_id, ctx.user.id, signal_id, "telegram",
                     status, datetime.now(UTC).isoformat() if ok else None,
                     None if ok else "send failed", self._dedup_key(signal_id, "telegram"),
                     datetime.now(UTC).isoformat()),
                )
            record(actor=ctx.user, action="publishing.telegram",
                   target_type="signal", target_id=signal_id,
                   detail={"status": status})
            return {"sent": ok, "status": status}
        finally:
            conn.close()

    def publish_square(self, signal_id: str | None, ctx: AccessContext,
                      template: str = "default") -> dict:
        config = self.get_config(ctx)
        if not config.get("square_enabled"):
            return {"sent": False, "reason": "square not enabled"}

        conn = self._conn()
        try:
            # Check daily count
            today = datetime.now(UTC).strftime("%Y-%m-%d")
            key = f"{ctx.user.id}:{today}"
            count_today = self._square_today.get(key, 0)
            limit = config["square_daily_limit"]

            if count_today >= limit:
                behavior = config["square_limit_behavior"]
                if behavior == "stop_square":
                    return {"sent": False, "reason": f"daily limit ({limit}) reached", "rate_limited": True}
                # queue — mark as pending
                pub_id = str(uuid.uuid4())
                with self._lock:
                    conn.execute(
                        "INSERT INTO publications VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (pub_id, ctx.user.id, signal_id, "binance_square",
                         "pending", None, None, self._dedup_key(signal_id, "binance_square"),
                         datetime.now(UTC).isoformat()),
                    )
                return {"sent": False, "reason": "queued: limit reached", "queued": True}

            # Actually post
            message = self._build_message(signal_id, ctx, template)
            ok = self._post_square(message, config, ctx)
            status = "sent" if ok else "failed"
            self._square_today[key] = count_today + 1

            pub_id = str(uuid.uuid4())
            with self._lock:
                conn.execute(
                    "INSERT INTO publications VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (pub_id, ctx.user.id, signal_id, "binance_square",
                     status, datetime.now(UTC).isoformat() if ok else None,
                     None if ok else "post failed",
                     self._dedup_key(signal_id, "binance_square"),
                     datetime.now(UTC).isoformat()),
                )
            record(actor=ctx.user, action="publishing.square",
                   target_type="signal", target_id=signal_id,
                   detail={"status": status})
            return {"sent": ok, "status": status}
        finally:
            conn.close()

    def list_publications(self, ctx: AccessContext, limit: int = 50) -> list[dict]:
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT id, signal_id, channel, status, posted_at, error_message, created_at "
                "FROM publications WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
                (ctx.user.id, limit)).fetchall()
            return [{"id": r[0], "signal_id": r[1], "channel": r[2],
                     "status": r[3], "posted_at": r[4], "error_message": r[5],
                     "created_at": r[6]} for r in rows]
        finally:
            conn.close()

    def _build_message(self, signal_id: str | None, ctx: AccessContext, template: str) -> str:
        if not signal_id:
            return f"ERMIS Signal Update — {datetime.now(UTC).strftime('%H:%M UTC')}"
        try:
            from app.services.signal_service import SignalService
            from app.notifications.signal_publisher import format_signal
            sig = SignalService(self._db_path).get(signal_id, ctx)
            return format_signal(sig)
        except Exception as exc:
            raise RuntimeError(f"could not build message for signal {signal_id}") from exc

    def _post_square(self, message: str, config: dict, ctx: AccessContext) -> bool:
        try:
            import urllib.request
            api_key = ""
            row = None
            conn2 = self._conn()
            try:
                row = conn2.execute(
                    "SELECT square_api_key_enc FROM publishing_configs WHERE user_id = ?",
                    (ctx.user.id,)).fetchone()
            finally:
                conn2.close()
            if row and row[0]:
                api_key = decrypt(row[0])
            endpoint = config.get("square_endpoint") or "https://api.binance.com/square/v1/posts"
            data = json.dumps({"content": message}).encode()
            req = urllib.request.Request(
                endpoint,
                data=data,
                headers={"Content-Type": "application/json",
                         "X-Binance-Square-API-Key": api_key},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status in (200, 201, 202)
        except Exception as exc:
            logger.warning("Square publish failed: %s", exc)
            return False

    def _dedup_key(self, signal_id: str | None, channel: str) -> str:
        return f"{signal_id}:{channel}:{datetime.now(UTC).strftime('%Y%m%d')}"
