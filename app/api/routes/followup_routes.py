"""Followup routes: /followups/* — create, list, get."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies import get_access_context
from app.core.errors import NotFoundError
from app.core.rbac import AccessContext

router = APIRouter(prefix="/followups", tags=["followups"])


@router.get("")
def list_followups(
    signal_id: str | None = None,
    ctx: AccessContext = Depends(get_access_context),
):
    from app.services.followup_service import FollowupService
    svc = FollowupService()
    if not signal_id:
        raise HTTPException(status_code=400, detail="signal_id query param required")
    return [f.to_dict() for f in svc.list_for_signal(signal_id, ctx)]


@router.post("")
def create_followup(
    payload: dict,
    ctx: AccessContext = Depends(get_access_context),
):
    from app.services.followup_service import FollowupService
    svc = FollowupService()
    try:
        f = svc.create(payload, ctx)
        # Fire automation
        try:
            from app.services.automation_engine import AutomationEngine
            AutomationEngine().on_followup(f.id, f.event_type.value, ctx)
        except Exception:
            pass
        return f.to_dict()
    except Exception as e:
        if hasattr(e, "http_status"):
            raise HTTPException(status_code=e.http_status, detail=e.message)
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{followup_id}")
def get_followup(
    followup_id: str,
    ctx: AccessContext = Depends(get_access_context),
):
    from app.services.followup_service import FollowupService
    svc = FollowupService()
    try:
        return svc.get(followup_id, ctx).to_dict()
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=e.message)
