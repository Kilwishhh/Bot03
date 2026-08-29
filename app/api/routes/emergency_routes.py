"""Emergency routes: /emergency/* — pause/resume at 4 scopes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies import get_access_context
from app.core.errors import ConflictError, ForbiddenError, NotFoundError, ValidationError
from app.core.rbac import AccessContext
from app.domain.connection import EmergencyScope

router = APIRouter(prefix="/emergency", tags=["emergency"])


@router.get("/status")
def list_active_pauses(
    scope: str | None = None,
    ctx: AccessContext = Depends(get_access_context),
):
    from app.services.emergency_service import EmergencyService
    return EmergencyService().list_active(ctx, scope=scope)


@router.post("/pause")
def pause(
    payload: dict,
    ctx: AccessContext = Depends(get_access_context),
):
    from app.services.emergency_service import EmergencyService
    from app.domain.connection import EmergencyScope
    svc = EmergencyService()
    try:
        scope = payload.get("scope", EmergencyScope.USER.value)
        # User-scope pauses without explicit target default to the caller's own ID
        scope_target = payload.get("scope_target")
        if scope == EmergencyScope.USER.value and not scope_target:
            scope_target = ctx.user.id
        p = svc.pause(
            scope=scope,
            scope_target=scope_target,
            reason=payload.get("reason", ""),
            ctx=ctx,
            close_positions=bool(payload.get("close_positions", False)),
            expires_at=payload.get("expires_at"),
        )
        return {
            "id": p.id, "scope": p.scope.value, "scope_target": p.scope_target,
            "reason": p.reason, "close_positions": p.close_positions,
            "created_at": p.created_at.isoformat(),
        }
    except (ForbiddenError, ValidationError) as e:
        raise HTTPException(status_code=e.http_status, detail=e.message)


@router.post("/resume/{pause_id}")
def resume(
    pause_id: str,
    ctx: AccessContext = Depends(get_access_context),
):
    from app.services.emergency_service import EmergencyService
    svc = EmergencyService()
    try:
        svc.resume(pause_id, ctx)
        return {"resumed": True}
    except (NotFoundError, ForbiddenError, ConflictError) as e:
        raise HTTPException(status_code=e.http_status, detail=e.message)
