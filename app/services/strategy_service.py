"""Strategy service: CRUD + lifecycle event log + version snapshotting."""

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
from app.domain.strategy import (
    EntryConfig,
    ExecutionMode,
    ExecutionVenue,
    ExitConfig,
    LifecycleState,
    RiskConfig,
    Strategy,
    StrategyVersion,
    Timeframe,
)


class StrategyService:
    def __init__(self, db_path: str = "trading.db") -> None:
        self._db_path = db_path
        self._lock = threading.RLock()

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(self._db_path, check_same_thread=False, isolation_level=None)

    def create(self, payload: dict[str, Any], ctx: AccessContext) -> Strategy:
        ctx.require_active()
        strategy_id = str(uuid.uuid4())
        now = datetime.now(UTC).isoformat()
        entry = EntryConfig.from_dict(payload.get("entry_config", {}))
        exit_cfg = ExitConfig.from_dict(payload.get("exit_config", {}))
        risk = RiskConfig.from_dict(payload.get("risk_config", {}))
        mode = ExecutionMode(payload.get("execution_mode", "paper"))
        venue = ExecutionVenue(payload.get("execution_venue", "binance"))
        tf = Timeframe(payload.get("timeframe", "15m"))

        conn = self._conn()
        try:
            with self._lock:
                conn.execute(
                    "INSERT INTO strategies VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        strategy_id, ctx.user.id,
                        payload["name"], payload.get("description"),
                        1, LifecycleState.DRAFT.value,
                        mode.value, venue.value, payload["market"], tf.value,
                        json.dumps(entry.to_dict()),
                        json.dumps(exit_cfg.to_dict()),
                        json.dumps(risk.to_dict()),
                        payload.get("template_name"),
                        json.dumps(payload.get("template_params", {})),
                        now, now,
                    ),
                )
                # Initial lifecycle event
                conn.execute(
                    "INSERT INTO strategy_lifecycle_events "
                    "(strategy_id, from_state, to_state, actor_user_id, actor_role, reason, created_at) "
                    "VALUES (?, NULL, ?, ?, ?, ?, ?)",
                    (
                        strategy_id, LifecycleState.DRAFT.value,
                        ctx.user.id,
                        (ctx.user.role.value if hasattr(ctx.user.role, "value") else str(ctx.user.role)),
                        "created", now,
                    ),
                )
            record(actor=ctx.user, action="strategy.create", target_type="strategy",
                   target_id=strategy_id, detail={"name": payload["name"]})
            return self.get(strategy_id, ctx)
        finally:
            conn.close()

    def get(self, strategy_id: str, ctx: AccessContext) -> Strategy:
        conn = self._conn()
        try:
            row = conn.execute("SELECT * FROM strategies WHERE id = ?", (strategy_id,)).fetchone()
            if not row:
                raise errors.NotFoundError("strategy not found")
            s = self._row_to_strategy(row)
            ctx.require_owner(s.user_id)
            return s
        finally:
            conn.close()

    def list(self, ctx: AccessContext, state: str | None = None,
             market: str | None = None) -> list[Strategy]:
        conn = self._conn()
        try:
            q = "SELECT * FROM strategies WHERE user_id = ?"
            params: list[Any] = [ctx.user.id]
            if state:
                q += " AND lifecycle_state = ?"
                params.append(state)
            if market:
                q += " AND market = ?"
                params.append(market)
            q += " ORDER BY updated_at DESC"
            return [self._row_to_strategy(r) for r in conn.execute(q, params).fetchall()]
        finally:
            conn.close()

    def list_all(self, ctx: AccessContext, state: str | None = None) -> list[Strategy]:
        ctx.require_admin()
        conn = self._conn()
        try:
            q = "SELECT * FROM strategies"
            params: list = []
            if state:
                q += " WHERE lifecycle_state = ?"
                params.append(state)
            q += " ORDER BY updated_at DESC"
            return [self._row_to_strategy(r) for r in conn.execute(q, params).fetchall()]
        finally:
            conn.close()

    def update(self, strategy: Strategy, ctx: AccessContext) -> Strategy:
        ctx.require_owner(strategy.user_id)
        now = datetime.now(UTC).isoformat()
        conn = self._conn()
        try:
            with self._lock:
                # snapshot current version
                snapshot_id = str(uuid.uuid4())
                snap = {
                    "name": strategy.name, "description": strategy.description,
                    "lifecycle_state": strategy.lifecycle_state.value,
                    "execution_mode": strategy.execution_mode.value,
                    "execution_venue": strategy.execution_venue.value,
                    "market": strategy.market, "timeframe": strategy.timeframe.value,
                    "entry_config": strategy.entry_config.to_dict(),
                    "exit_config": strategy.exit_config.to_dict(),
                    "risk_config": strategy.risk_config.to_dict(),
                    "template_name": strategy.template_name,
                    "template_params": strategy.template_params,
                }
                conn.execute(
                    "INSERT INTO strategy_versions VALUES (?, ?, ?, ?, ?)",
                    (snapshot_id, strategy.id, strategy.version, json.dumps(snap), now),
                )
                conn.execute(
                    "UPDATE strategies SET name=?, description=?, version=?, "
                    "execution_mode=?, execution_venue=?, market=?, timeframe=?, "
                    "entry_config=?, exit_config=?, risk_config=?, template_name=?, "
                    "template_params=?, updated_at=? WHERE id=?",
                    (
                        strategy.name, strategy.description, strategy.version + 1,
                        strategy.execution_mode.value, strategy.execution_venue.value,
                        strategy.market, strategy.timeframe.value,
                        json.dumps(strategy.entry_config.to_dict()),
                        json.dumps(strategy.exit_config.to_dict()),
                        json.dumps(strategy.risk_config.to_dict()),
                        strategy.template_name,
                        json.dumps(strategy.template_params),
                        now, strategy.id,
                    ),
                )
            record(actor=ctx.user, action="strategy.update", target_type="strategy",
                   target_id=strategy.id)
            return self.get(strategy.id, ctx)
        finally:
            conn.close()

    def delete(self, strategy_id: str, ctx: AccessContext) -> None:
        s = self.get(strategy_id, ctx)
        if s.lifecycle_state == LifecycleState.LIVE:
            raise errors.ConflictError("cannot delete a LIVE strategy; stop it first")
        conn = self._conn()
        try:
            with self._lock:
                conn.execute("DELETE FROM strategies WHERE id = ?", (strategy_id,))
            record(actor=ctx.user, action="strategy.delete", target_type="strategy",
                   target_id=strategy_id)
        finally:
            conn.close()

    def get_versions(self, strategy_id: str, ctx: AccessContext) -> list[StrategyVersion]:
        self.get(strategy_id, ctx)  # permission check
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT id, strategy_id, version, config_snapshot, created_at "
                "FROM strategy_versions WHERE strategy_id = ? ORDER BY version DESC",
                (strategy_id,)).fetchall()
            return [StrategyVersion(
                id=r[0], strategy_id=r[1], version=r[2],
                config_snapshot=json.loads(r[3]) if r[3] else {},
                created_at=datetime.fromisoformat(r[4]) if r[4] else datetime.now(UTC),
            ) for r in rows]
        finally:
            conn.close()

    def record_lifecycle_event(self, strategy_id: str, from_state: LifecycleState | None,
                               to_state: LifecycleState, actor_user_id: str,
                               actor_role: str, reason: str | None) -> None:
        conn = self._conn()
        try:
            with self._lock:
                conn.execute(
                    "INSERT INTO strategy_lifecycle_events "
                    "(strategy_id, from_state, to_state, actor_user_id, actor_role, reason, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        strategy_id,
                        from_state.value if from_state else None,
                        to_state.value,
                        actor_user_id, actor_role, reason,
                        datetime.now(UTC).isoformat(),
                    ),
                )
        finally:
            conn.close()

    def get_lifecycle_events(self, strategy_id: str, ctx: AccessContext) -> list[dict]:
        self.get(strategy_id, ctx)
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT id, from_state, to_state, actor_user_id, actor_role, reason, created_at "
                "FROM strategy_lifecycle_events WHERE strategy_id = ? ORDER BY id DESC",
                (strategy_id,)).fetchall()
            return [{
                "id": r[0], "from_state": r[1], "to_state": r[2],
                "actor_user_id": r[3], "actor_role": r[4], "reason": r[5],
                "created_at": r[6],
            } for r in rows]
        finally:
            conn.close()

    def _row_to_strategy(self, row: tuple) -> Strategy:
        return Strategy(
            id=row[0], user_id=row[1], name=row[2], description=row[3], version=row[4],
            lifecycle_state=LifecycleState(row[5]),
            execution_mode=ExecutionMode(row[6]),
            execution_venue=ExecutionVenue(row[7]),
            market=row[8], timeframe=Timeframe(row[9]),
            entry_config=EntryConfig.from_dict(json.loads(row[10]) if row[10] else {}),
            exit_config=ExitConfig.from_dict(json.loads(row[11]) if row[11] else {}),
            risk_config=RiskConfig.from_dict(json.loads(row[12]) if row[12] else {}),
            template_name=row[13],
            template_params=json.loads(row[14]) if row[14] else {},
            created_at=datetime.fromisoformat(row[15]) if row[15] else datetime.now(UTC),
            updated_at=datetime.fromisoformat(row[16]) if row[16] else datetime.now(UTC),
        )
