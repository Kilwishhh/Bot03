"""Emergency service: 3-scope pause/resume (strategy | user | platform)."""

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
from app.domain.connection import EmergencyPause, EmergencyScope


class EmergencyService:
    def __init__(self, db_path: str = "trading.db") -> None:
        self._db_path = db_path
        self._lock = threading.RLock()

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(self._db_path, check_same_thread=False, isolation_level=None)

    def pause(
        self,
        scope: str,
        scope_target: str | None,
        reason: str,
        ctx: AccessContext,
        close_positions: bool = False,
        expires_at: str | None = None,
    ) -> EmergencyPause:
        if scope == EmergencyScope.PLATFORM.value and not ctx.is_admin():
            raise errors.ForbiddenError("only admin can pause at platform scope")
        if scope == EmergencyScope.USER.value and not ctx.is_admin() and scope_target != ctx.user.id:
            raise errors.ForbiddenError("can only pause your own user scope unless admin")
        if not reason or not reason.strip():
            raise errors.ValidationError("reason is required for emergency pause")

        pause_id = str(uuid.uuid4())
        now = datetime.now(UTC).isoformat()
        conn = self._conn()
        try:
            with self._lock:
                conn.execute(
                    "INSERT INTO emergency_pauses VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (pause_id, scope, scope_target, ctx.user.id,
                     (ctx.user.role.value if hasattr(ctx.user.role, "value") else str(ctx.user.role)),
                     reason, 1 if close_positions else 0, now, expires_at),
                )
            record(actor=ctx.user, action="emergency.pause",
                   target_type=f"emergency:{scope}", target_id=scope_target,
                   detail={"reason": reason, "close_positions": close_positions,
                           "expires_at": expires_at})
            return self._row_to_pause((pause_id, scope, scope_target, ctx.user.id,
                                      (ctx.user.role.value if hasattr(ctx.user.role, "value") else str(ctx.user.role)),
                                      reason, 1 if close_positions else 0, now, expires_at, None))
        finally:
            conn.close()

    def resume(
        self,
        pause_id: str,
        ctx: AccessContext,
    ) -> None:
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT actor_user_id, scope, scope_target, resumed_at FROM emergency_pauses WHERE id = ?",
                (pause_id,)).fetchone()
            if not row:
                raise errors.NotFoundError("pause not found")
            if not ctx.is_admin() and row[0] != ctx.user.id:
                raise errors.ForbiddenError("can only resume your own pauses unless admin")
            if row[3]:
                raise errors.ConflictError("pause already resumed")
            with self._lock:
                conn.execute(
                    "UPDATE emergency_pauses SET resumed_at = ? WHERE id = ?",
                    (datetime.now(UTC).isoformat(), pause_id),
                )
            record(actor=ctx.user, action="emergency.resume",
                   target_type=f"emergency:{row[1]}", target_id=row[2],
                   detail={"pause_id": pause_id})
        finally:
            conn.close()

    def list_active(self, ctx: AccessContext, scope: str | None = None) -> list[dict]:
        conn = self._conn()
        try:
            q = "SELECT * FROM emergency_pauses WHERE resumed_at IS NULL"
            params: list = []
            if scope:
                q += " AND scope = ?"
                params.append(scope)
            q += " ORDER BY created_at DESC"
            rows = conn.execute(q, params).fetchall()
            # Filter by access: own + global
            if not ctx.is_admin():
                rows = [r for r in rows if r[3] == ctx.user.id
                        or r[1] == EmergencyScope.PLATFORM.value]
            return [self._pause_to_dict(self._row_to_pause(r)) for r in rows]
        finally:
            conn.close()

    def get_pause_status(self, strategy_id: str | None = None, user_id: str | None = None,
                        venue: str | None = None, ctx: AccessContext | None = None) -> dict:
        """Check if any active pause applies to a given target. Strategy/user/integration/platform."""
        conn = self._conn()
        try:
            now = datetime.now(UTC).isoformat()
            q = "SELECT * FROM emergency_pauses WHERE resumed_at IS NULL"
            params: list = []
            if strategy_id:
                q += " AND ((scope = 'strategy' AND scope_target = ?) OR scope = 'platform')"
                params.append(strategy_id)
            if user_id:
                q += " AND ((scope = 'user' AND scope_target = ?) OR scope = 'platform')"
                params.append(user_id)
            if venue:
                q += " AND ((scope = 'integration' AND scope_target = ?) OR scope = 'platform')"
                params.append(venue)
            q += " AND (expires_at IS NULL OR expires_at > ?)"
            params.append(now)
            rows = conn.execute(q, params).fetchall()
            return {
                "is_paused": len(rows) > 0,
                "pauses": [self._pause_to_dict(self._row_to_pause(r)) for r in rows],
            }
        finally:
            conn.close()

    def _row_to_pause(self, row: tuple) -> EmergencyPause:
        return EmergencyPause(
            id=row[0], scope=EmergencyScope(row[1]), scope_target=row[2],
            actor_user_id=row[3], actor_role=row[4], reason=row[5],
            close_positions=bool(row[6]),
            created_at=datetime.fromisoformat(row[7]) if row[7] else datetime.now(UTC),
            expires_at=datetime.fromisoformat(row[8]) if row[8] else None,
            resumed_at=datetime.fromisoformat(row[9]) if row[9] else None,
        )

    def _pause_to_dict(self, p: EmergencyPause) -> dict:
        return {
            "id": p.id, "scope": p.scope.value, "scope_target": p.scope_target,
            "actor_user_id": p.actor_user_id, "actor_role": p.actor_role,
            "reason": p.reason, "close_positions": p.close_positions,
            "created_at": p.created_at.isoformat() if hasattr(p.created_at, "isoformat") else p.created_at,
            "expires_at": p.expires_at.isoformat() if p.expires_at and hasattr(p.expires_at, "isoformat") else p.expires_at,
            "resumed_at": p.resumed_at.isoformat() if p.resumed_at and hasattr(p.resumed_at, "isoformat") else p.resumed_at,
        }
