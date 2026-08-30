"""Admin routes: /admin/users/*, /admin/audit/*."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

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
