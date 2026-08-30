"""Automation engine: TRIGGER → CONDITIONS → ACTIONS pipeline.

Runs asynchronously in a background thread. Each rule firing is idempotent:
enforced by a unique dedup_key (rule_id + signal_id + followup_id).
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from typing import Any

from app.core import errors
from app.core.rbac import AccessContext
from app.domain.automation import (
    AutomationAction,
    AutomationActionType,
    AutomationCondition,
    AutomationRule,
    AutomationTrigger,
)

logger = logging.getLogger(__name__)


class AutomationEngine:
    def __init__(self, db_path: str = "trading.db") -> None:
        self._db_path = db_path
        self._lock = threading.RLock()
        self._executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="auto_")

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(self._db_path, check_same_thread=False, isolation_level=None)

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def create_rule(self, payload: dict[str, Any], ctx: AccessContext) -> AutomationRule:
        ctx.require_active()
        rule_id = str(uuid.uuid4())
        now = datetime.now(UTC).isoformat()
        conn = self._conn()
        try:
            conditions = json.dumps([
                c.to_dict() if hasattr(c, "to_dict") else c
                for c in self._parse_conditions(payload.get("conditions", []))
            ])
            actions = json.dumps([
                a.to_dict() if hasattr(a, "to_dict") else a
                for a in self._parse_actions(payload.get("actions", []))
            ])
            with self._lock:
                conn.execute(
                    "INSERT INTO automation_rules VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        rule_id, ctx.user.id, payload.get("strategy_id"),
                        payload["name"], payload["trigger"],
                        conditions, actions,
                        1 if payload.get("enabled", True) else 0, now, now,
                    ),
                )
            return self.get_rule(rule_id, ctx)
        finally:
            conn.close()

    def get_rule(self, rule_id: str, ctx: AccessContext) -> AutomationRule:
        conn = self._conn()
        try:
            row = conn.execute("SELECT * FROM automation_rules WHERE id = ?", (rule_id,)).fetchone()
            if not row:
                raise errors.NotFoundError("rule not found")
            r = self._row_to_rule(row)
            ctx.require_owner(r.user_id)
            return r
        finally:
            conn.close()

    def list_rules(self, ctx: AccessContext, strategy_id: str | None = None,
                   trigger: str | None = None) -> list[AutomationRule]:
        conn = self._conn()
        try:
            q = "SELECT * FROM automation_rules WHERE user_id = ?"
            params: list = [ctx.user.id]
            if strategy_id:
                q += " AND (strategy_id = ? OR strategy_id IS NULL)"
                params.append(strategy_id)
            if trigger:
                q += " AND trigger = ?"
                params.append(trigger)
            q += " ORDER BY created_at DESC"
            return [self._row_to_rule(r) for r in conn.execute(q, params).fetchall()]
        finally:
            conn.close()

    def update_rule(self, rule_id: str, payload: dict[str, Any], ctx: AccessContext) -> AutomationRule:
        r = self.get_rule(rule_id, ctx)
        conn = self._conn()
        try:
            with self._lock:
                conn.execute(
                    "UPDATE automation_rules SET name=?, trigger=?, conditions=?, "
                    "actions=?, enabled=?, updated_at=? WHERE id=?",
                    (
                        payload.get("name", r.name),
                        payload.get("trigger", r.trigger.value),
                        json.dumps(payload.get("conditions", [])),
                        json.dumps(payload.get("actions", [])),
                        1 if payload.get("enabled", r.enabled) else 0,
                        datetime.now(UTC).isoformat(), rule_id,
                    ),
                )
            return self.get_rule(rule_id, ctx)
        finally:
            conn.close()

    def delete_rule(self, rule_id: str, ctx: AccessContext) -> None:
        self.get_rule(rule_id, ctx)
        conn = self._conn()
        try:
            with self._lock:
                conn.execute("DELETE FROM automation_rules WHERE id = ?", (rule_id,))
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Engine: trigger firing
    # ------------------------------------------------------------------

    def on_signal_generated(self, signal_id: str, ctx: AccessContext) -> None:
        """Call this when a new signal is created. Fires matching rules asynchronously."""
        self._executor.submit(self._fire_rules, "signal_generated", signal_id, None, ctx)

    def on_followup(self, followup_id: str, event_type: str, ctx: AccessContext) -> None:
        """Call this when a follow-up event is created."""
        self._executor.submit(self._fire_rules, event_type, None, followup_id, ctx)

    def _fire_rules(
        self, trigger: str, signal_id: str | None,
        followup_id: str | None, ctx: AccessContext,
    ) -> None:
        """Evaluate + execute all matching rules for a trigger."""
        try:
            conn = self._conn()
            try:
                rows = conn.execute(
                    "SELECT * FROM automation_rules WHERE trigger = ? AND enabled = 1 "
                    "AND (strategy_id IS NULL OR strategy_id IN "
                    "(SELECT strategy_id FROM signals WHERE id = ?))",
                    (trigger, signal_id) if signal_id else (trigger, ""),
                ).fetchall()
                for row in rows:
                    rule = self._row_to_rule(row)
                    dedup_key = f"{rule.id}:{signal_id or ''}:{followup_id or ''}"
                    if self._is_deduped(rule.id, dedup_key, conn):
                        continue
                    self._execute_rule(rule, signal_id, followup_id, dedup_key, ctx)
            finally:
                conn.close()
        except Exception as exc:
            logger.error("AutomationEngine._fire_rules failed: %s", exc)

    def _is_deduped(self, rule_id: str, dedup_key: str, conn: sqlite3.Connection) -> bool:
        row = conn.execute(
            "SELECT 1 FROM automation_events WHERE rule_id = ? AND dedup_key = ?",
            (rule_id, dedup_key)).fetchone()
        return row is not None

    def _execute_rule(
        self, rule: AutomationRule, signal_id: str | None,
        followup_id: str | None, dedup_key: str, ctx: AccessContext,
    ) -> None:
        evt_id = str(uuid.uuid4())
        now = datetime.now(UTC).isoformat()
        conn = self._conn()
        try:
            with self._lock:
                conn.execute(
                    "INSERT INTO automation_events VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (evt_id, rule.id, signal_id, followup_id, "running",
                     None, 0, dedup_key, now, None),
                )
            results: list[dict] = []
            for action in rule.actions:
                try:
                    result = self._run_action(action, signal_id, followup_id, ctx)
                    results.append({"action": action.type.value, "ok": True, "result": result})
                except Exception as exc:
                    logger.warning("Action %s failed: %s", action.type, exc)
                    results.append({"action": action.type.value, "ok": False, "error": str(exc)})
            with self._lock:
                conn.execute(
                    "UPDATE automation_events SET status=?, result=?, attempts=attempts+1, "
                    "completed_at=? WHERE id=?",
                    ("completed", json.dumps(results), now, evt_id),
                )
        finally:
            conn.close()

    def _run_action(self, action: AutomationAction, signal_id: str | None,
                   followup_id: str | None, ctx: AccessContext) -> dict:
        from app.services.publishing_service import PublishingService
        svc = PublishingService(db_path=self._db_path)

        match action.type:
            case AutomationActionType.TELEGRAM_PUBLISH:
                return svc.publish_telegram(signal_id, ctx, template=action.params.get("template"))
            case AutomationActionType.SQUARE_PUBLISH:
                return svc.publish_square(signal_id, ctx, template=action.params.get("template"))
            case AutomationActionType.NOTIFICATION:
                return {"notified": True, "severity": action.params.get("severity", "info"),
                        "message": action.params.get("message", "")}
            case _:
                return {"skipped": True, "reason": f"action type {action.type} not implemented"}

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _parse_conditions(self, raw: list) -> list[AutomationCondition]:
        return [AutomationCondition.from_dict(c) if isinstance(c, dict) else c for c in raw]

    def _parse_actions(self, raw: list) -> list[AutomationAction]:
        return [AutomationAction.from_dict(a) if isinstance(a, dict) else a for a in raw]

    def _row_to_rule(self, row: tuple) -> AutomationRule:
        conditions = json.loads(row[5]) if row[5] else []
        actions = json.loads(row[6]) if row[6] else []
        return AutomationRule(
            id=row[0], user_id=row[1], strategy_id=row[2],
            name=row[3], trigger=AutomationTrigger(row[4]),
            conditions=[AutomationCondition.from_dict(c) for c in conditions],
            actions=[AutomationAction.from_dict(a) for a in actions],
            enabled=bool(row[7]),
            created_at=datetime.fromisoformat(row[8]) if row[8] else datetime.now(UTC),
            updated_at=datetime.fromisoformat(row[9]) if row[9] else datetime.now(UTC),
        )
