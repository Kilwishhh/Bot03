"""Followup service: TP/SL timeline tracking per signal."""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from datetime import UTC, datetime
from typing import Any

from app.core import errors
from app.core.audit import record
from app.core.rbac import AccessContext
from app.domain.followup import Followup, FollowupEventType, FollowupExecutionStatus


class FollowupService:
    def __init__(self, db_path: str = "trading.db") -> None:
        self._db_path = db_path
        self._lock = threading.RLock()

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(self._db_path, check_same_thread=False, isolation_level=None)

    def create(self, payload: dict[str, Any], ctx: AccessContext) -> Followup:
        """Record a new follow-up event on a signal."""
        signal_id = payload.get("signal_id")
        if not signal_id:
            raise errors.ValidationError("signal_id is required")
        # Verify signal exists + user owns it
        from app.services.signal_service import SignalService
        sig_svc = SignalService(self._db_path)
        sig_svc.get(signal_id, ctx)

        followup_id = str(uuid.uuid4())
        now = datetime.now(UTC).isoformat()
        conn = self._conn()
        try:
            with self._lock:
                conn.execute(
                    "INSERT INTO signal_followups VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        followup_id, signal_id,
                        payload["event_type"],
                        json.dumps(payload.get("event_data", {})),
                        json.dumps(payload.get("publishing_status", {})),
                        payload.get("execution_status", "pending"),
                        now,
                    ),
                )
            record(actor=ctx.user, action="followup.create",
                   target_type="signal_followup", target_id=followup_id,
                   detail={"signal_id": signal_id, "event_type": payload["event_type"]})
            return self.get(followup_id, ctx)
        finally:
            conn.close()

    def get(self, followup_id: str, ctx: AccessContext) -> Followup:
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT f.*, s.user_id FROM signal_followups f "
                "JOIN signals s ON f.signal_id = s.id "
                "WHERE f.id = ?", (followup_id,)).fetchone()
            if not row:
                raise errors.NotFoundError("followup not found")
            f = self._row_to_followup(row)
            if row[-1] != ctx.user.id and not ctx.is_admin():
                raise errors.NotFoundError("followup not found")
            return f
        finally:
            conn.close()

    def list_for_signal(self, signal_id: str, ctx: AccessContext) -> list[Followup]:
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT f.* FROM signal_followups f "
                "JOIN signals s ON f.signal_id = s.id "
                "WHERE f.signal_id = ? AND s.user_id = ? "
                "ORDER BY f.created_at ASC",
                (signal_id, ctx.user.id)).fetchall()
            return [self._row_to_followup(r) for r in rows]
        finally:
            conn.close()

    def update_publishing_status(self, followup_id: str,
                                publishing_status: dict[str, str],
                                ctx: AccessContext) -> None:
        conn = self._conn()
        try:
            with self._lock:
                conn.execute(
                    "UPDATE signal_followups SET publishing_status = ? WHERE id = ?",
                    (json.dumps(publishing_status), followup_id),
                )
        finally:
            conn.close()

    def update_execution_status(self, followup_id: str,
                               execution_status: str,
                               ctx: AccessContext) -> None:
        conn = self._conn()
        try:
            with self._lock:
                conn.execute(
                    "UPDATE signal_followups SET execution_status = ? WHERE id = ?",
                    (execution_status, followup_id),
                )
        finally:
            conn.close()

    def _row_to_followup(self, row: tuple) -> Followup:
        return Followup(
            id=row[0], signal_id=row[1],
            event_type=FollowupEventType(row[2]) if row[2] else FollowupEventType.NOTE,
            event_data=json.loads(row[3]) if row[3] else {},
            publishing_status=json.loads(row[4]) if row[4] else {},
            execution_status=FollowupExecutionStatus(row[5]) if row[5] else FollowupExecutionStatus.PENDING,
            created_at=datetime.fromisoformat(row[6]) if row[6] else datetime.now(UTC),
        )
