"""Automation routes: /automation/rules/* — CRUD + listing events."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies import get_access_context
from app.core.errors import NotFoundError
from app.core.rbac import AccessContext

router = APIRouter(prefix="/automation", tags=["automation"])


@router.get("/rules")
def list_rules(
    strategy_id: str | None = None,
    trigger: str | None = None,
    ctx: AccessContext = Depends(get_access_context),
):
    from app.services.automation_engine import AutomationEngine
    eng = AutomationEngine()
    return [r.to_dict() for r in eng.list_rules(ctx, strategy_id=strategy_id, trigger=trigger)]


@router.post("/rules")
def create_rule(
    payload: dict,
    ctx: AccessContext = Depends(get_access_context),
):
    from app.services.automation_engine import AutomationEngine
    eng = AutomationEngine()
    try:
        r = eng.create_rule(payload, ctx)
        return r.to_dict()
    except Exception as e:
        if hasattr(e, "http_status"):
            raise HTTPException(status_code=e.http_status, detail=e.message)
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/rules/{rule_id}")
def get_rule(
    rule_id: str,
    ctx: AccessContext = Depends(get_access_context),
):
    from app.services.automation_engine import AutomationEngine
    eng = AutomationEngine()
    try:
        return eng.get_rule(rule_id, ctx).to_dict()
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=e.message)


@router.patch("/rules/{rule_id}")
def update_rule(
    rule_id: str,
    payload: dict,
    ctx: AccessContext = Depends(get_access_context),
):
    from app.services.automation_engine import AutomationEngine
    eng = AutomationEngine()
    try:
        r = eng.update_rule(rule_id, payload, ctx)
        return r.to_dict()
    except Exception as e:
        if hasattr(e, "http_status"):
            raise HTTPException(status_code=e.http_status, detail=e.message)
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/rules/{rule_id}")
def delete_rule(
    rule_id: str,
    ctx: AccessContext = Depends(get_access_context),
):
    from app.services.automation_engine import AutomationEngine
    eng = AutomationEngine()
    try:
        eng.delete_rule(rule_id, ctx)
        return {"deleted": True}
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=e.message)
