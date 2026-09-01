"""Admin routes: /admin/users/*, /admin/audit/*."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.core.errors import ForbiddenError, NotFoundError
from app.core.rbac import AccessContext

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users")
def list_users(
    ctx: AccessContext = Depends(__import__("app.api.dependencies", fromlist=["get_access_context"]).get_access_context),
):
    from app.services.user_service import UserService
    svc = UserService()
    try:
        users = svc.list_users(ctx)
        return [{"id": u.id, "email": u.email, "display_name": u.display_name,
                 "role": str(u.role), "status": str(u.status),
                 "created_at": u.created_at.isoformat() if hasattr(u.created_at, "isoformat") else u.created_at}
                for u in users]
    except ForbiddenError as e:
        raise HTTPException(status_code=403, detail=e.message)


@router.get("/users/{user_id}")
def get_user(
    user_id: str,
    ctx: AccessContext = Depends(__import__("app.api.dependencies", fromlist=["get_access_context"]).get_access_context),
):
    from app.services.user_service import UserService
    svc = UserService()
    try:
        users = svc.list_users(ctx)
        for u in users:
            if u.id == user_id:
                return {"id": u.id, "email": u.email, "display_name": u.display_name,
                        "role": str(u.role), "status": str(u.status),
                        "created_at": u.created_at.isoformat()}
        raise HTTPException(status_code=404, detail="user not found")
    except ForbiddenError as e:
        raise HTTPException(status_code=403, detail=e.message)


@router.post("/users/{user_id}/suspend")
def suspend_user(
    user_id: str,
    ctx: AccessContext = Depends(__import__("app.api.dependencies", fromlist=["get_access_context"]).get_access_context),
):
    from app.services.user_service import UserService
    svc = UserService()
    try:
        u = svc.suspend_user(user_id, ctx)
        return {"id": u.id, "status": str(u.status)}
    except (ForbiddenError, NotFoundError) as e:
        raise HTTPException(status_code=e.http_status, detail=e.message)


@router.get("/strategies")
def admin_list_strategies(
    state: str | None = None,
    ctx: AccessContext = Depends(__import__("app.api.dependencies", fromlist=["get_access_context"]).get_access_context),
):
    from app.services.strategy_service import StrategyService
    svc = StrategyService()
    try:
        strategies = svc.list_all(ctx, state=state)
        return [{"id": s.id, "user_id": s.user_id, "name": s.name,
                 "lifecycle_state": s.lifecycle_state.value,
                 "execution_mode": s.execution_mode.value,
                 "market": s.market, "updated_at": s.updated_at.isoformat()}
                for s in strategies]
    except ForbiddenError as e:
        raise HTTPException(status_code=403, detail=e.message)


@router.get("/audit")
def audit_tail(
    limit: int = 50,
    action: str | None = None,
    actor_user_id: str | None = None,
    ctx: AccessContext = Depends(__import__("app.api.dependencies", fromlist=["get_access_context"]).get_access_context),
):
    from app.database.repository import get_default_repository
    ctx.require_admin()
    repo = get_default_repository()
    rows = repo.recent_audit(limit=limit, action=action, actor_user_id=actor_user_id)
    return [{"id": r[0], "actor_user_id": r[1], "actor_role": r[2],
             "action": r[3], "target_type": r[4], "target_id": r[5],
             "detail": r[6], "result": r[7], "created_at": r[8]} for r in rows]


@router.get("/system/health")
def admin_system_health(
    ctx: AccessContext = Depends(__import__("app.api.dependencies", fromlist=["get_access_context"]).get_access_context),
):
    from app.services.health_service import HealthService
    svc = HealthService()
    try:
        return svc.check_all(ctx)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/risk")
def admin_risk_snapshot(
    ctx: AccessContext = Depends(__import__("app.api.dependencies", fromlist=["get_access_context"]).get_access_context),
):
    """Return current risk-manager state for the live bot, if any."""
    from app.api.control import _controller
    ctx.require_admin()
    snapshot = {
        "bot_running": _controller.get("thread") is not None and _controller["thread"].is_alive()
                       if _controller.get("thread") else False,
        "risk": None,
    }
    runner = _controller.get("runner")
    if runner is not None and hasattr(runner, "cycle") and hasattr(runner.cycle, "orders"):
        risk = getattr(runner.cycle.orders, "risk", None)
        if risk is not None and hasattr(risk, "snapshot"):
            snapshot["risk"] = risk.snapshot()
    return snapshot


@router.post("/users/{user_id}/activate")
def activate_user(
    user_id: str,
    ctx: AccessContext = Depends(__import__("app.api.dependencies", fromlist=["get_access_context"]).get_access_context),
):
    from app.database.repository import get_default_repository
    ctx.require_admin()
    repo = get_default_repository()
    repo._connection.execute("UPDATE users SET status='active' WHERE id=?", (user_id,))
    return {"id": user_id, "status": "active"}


@router.delete("/users/{user_id}")
def delete_user(
    user_id: str,
    ctx: AccessContext = Depends(__import__("app.api.dependencies", fromlist=["get_access_context"]).get_access_context),
):
    ctx.require_admin()
    from app.database.repository import get_default_repository
    repo = get_default_repository()
    repo._connection.execute("DELETE FROM signal_followups WHERE signal_id IN (SELECT id FROM signals WHERE user_id=?)", (user_id,))
    repo._connection.execute("DELETE FROM signals WHERE user_id=?", (user_id,))
    repo._connection.execute("DELETE FROM users WHERE id=?", (user_id,))
    return {"id": user_id, "deleted": True}


@router.get("/strategies/{strategy_id}")
def get_strategy(
    strategy_id: str,
    ctx: AccessContext = Depends(__import__("app.api.dependencies", fromlist=["get_access_context"]).get_access_context),
):
    from app.services.strategy_service import StrategyService
    ctx.require_admin()
    svc = StrategyService()
    strategies = svc.list_all(ctx)
    for s in strategies:
        if s.id == strategy_id:
            return {"id": s.id, "user_id": s.user_id, "name": s.name,
                    "lifecycle_state": s.lifecycle_state.value,
                    "execution_mode": s.execution_mode.value,
                    "market": s.market, "updated_at": s.updated_at.isoformat()}
    raise HTTPException(status_code=404, detail="Strategy not found")


@router.patch("/strategies/{strategy_id}")
def admin_update_strategy(
    strategy_id: str,
    payload: dict,
    ctx: AccessContext = Depends(__import__("app.api.dependencies", fromlist=["get_access_context"]).get_access_context),
):
    """Admin-level PATCH: same fields as the user route but skips ownership check."""
    from app.api.routes.strategy_routes import _serialize
    from app.services.strategy_service import StrategyService
    ctx.require_admin()
    svc = StrategyService()
    try:
        strategies = svc.list_all(ctx)
        s = next((x for x in strategies if x.id == strategy_id), None)
        if s is None:
            raise HTTPException(status_code=404, detail="Strategy not found")
        for field in ("name", "description", "market", "template_name", "template_params"):
            if field in payload:
                setattr(s, field, payload[field])
        if "entry_config" in payload:
            from app.domain.strategy import EntryConfig
            s.entry_config = EntryConfig.from_dict(payload["entry_config"])
        if "exit_config" in payload:
            from app.domain.strategy import ExitConfig
            s.exit_config = ExitConfig.from_dict(payload["exit_config"])
        if "risk_config" in payload:
            from app.domain.strategy import RiskConfig
            s.risk_config = RiskConfig.from_dict(payload["risk_config"])
        if "execution_mode" in payload:
            from app.domain.strategy import ExecutionMode
            s.execution_mode = ExecutionMode(payload["execution_mode"])
        if "execution_venue" in payload:
            from app.domain.strategy import ExecutionVenue
            s.execution_venue = ExecutionVenue(payload["execution_venue"])
        if "timeframe" in payload:
            from app.domain.strategy import Timeframe
            s.timeframe = Timeframe(payload["timeframe"])
        return _serialize(svc.update(s, ctx))
    except HTTPException:
        raise
    except Exception as e:
        if hasattr(e, "http_status"):
            raise HTTPException(status_code=e.http_status, detail=e.message)
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/strategies/{strategy_id}/transition")
def admin_transition_strategy(
    strategy_id: str,
    payload: dict,
    ctx: AccessContext = Depends(__import__("app.api.dependencies", fromlist=["get_access_context"]).get_access_context),
):
    """Admin-level lifecycle transition. target_state ∈ {draft, paper, live, paused, archived, disabled}."""
    from app.api.routes.strategy_routes import _serialize
    from app.domain.strategy import LifecycleState
    from app.services.strategy_lifecycle import StrategyLifecycle
    from app.services.strategy_service import StrategyService
    ctx.require_admin()
    svc = StrategyService()
    lifecycle = StrategyLifecycle(svc)
    try:
        s = next((x for x in svc.list_all(ctx) if x.id == strategy_id), None)
        if s is None:
            raise HTTPException(status_code=404, detail="Strategy not found")
        target = LifecycleState(payload["target_state"])
        result = lifecycle.transition(
            s, target, ctx,
            reason=payload.get("reason"),
            confirm_live=payload.get("confirm_live", False),
            confirmation_string=payload.get("confirmation_string", ""),
        )
        return _serialize(result)
    except HTTPException:
        raise
    except Exception as e:
        if hasattr(e, "http_status"):
            raise HTTPException(status_code=e.http_status, detail=e.message)
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/control")
def admin_control(
    ctx: AccessContext = Depends(__import__("app.api.dependencies", fromlist=["get_access_context"]).get_access_context),
):
    ctx.require_admin()
    from app.api.control import _controller
    from app.database.repository import get_default_repository
    repo = get_default_repository()
    state = repo.control_state()
    return {
        "state": state[0] if state else "stopped",
        "bot_running": _controller.get("thread") is not None and _controller["thread"].is_alive(),
        "paused": _controller.get("paused", False),
    }


@router.post("/control/{action}")
def admin_control_action(
    action: str,
    ctx: AccessContext = Depends(__import__("app.api.dependencies", fromlist=["get_access_context"]).get_access_context),
):
    ctx.require_admin()
    from app.api.control import _controller
    from app.database.repository import get_default_repository
    repo = get_default_repository()
    if action == "stop":
        _controller["stop"] = True
        repo.set_control_state("stopped")
        return {"action": "stop", "state": "stopped"}
    if action == "pause":
        _controller["paused"] = True
        repo.set_control_state("paused")
        return {"action": "pause", "state": "paused"}
    if action == "resume":
        _controller["paused"] = False
        repo.set_control_state("running")
        return {"action": "resume", "state": "running"}
    raise HTTPException(status_code=400, detail=f"unknown action: {action}")


@router.get("/logs")
def admin_logs(
    limit: int = 100,
    since: str | None = None,
    ctx: AccessContext = Depends(__import__("app.api.dependencies", fromlist=["get_access_context"]).get_access_context),
):
    """Return the most recent server log lines (in-memory ring buffer)."""
    from app.utils.log_buffer import tail
    ctx.require_admin()
    return tail(n=limit, since=since)
