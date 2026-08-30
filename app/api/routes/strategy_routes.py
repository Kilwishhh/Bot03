"""Strategy routes: /strategies/* — CRUD + lifecycle + versions."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies import get_access_context
from app.core.errors import (
    ConflictError,
    ForbiddenError,
    LifecycleError,
    LiveDeploymentError,
    NotFoundError,
)
from app.core.rbac import AccessContext
from app.domain.strategy import LifecycleState

router = APIRouter(prefix="/strategies", tags=["strategies"])


def _serialize(s) -> dict:
    return {
        "id": s.id, "user_id": s.user_id, "name": s.name, "description": s.description,
        "version": s.version, "lifecycle_state": s.lifecycle_state.value,
        "execution_mode": s.execution_mode.value,
        "execution_venue": s.execution_venue.value,
        "market": s.market, "timeframe": s.timeframe.value,
        "entry_config": s.entry_config.to_dict(),
        "exit_config": s.exit_config.to_dict(),
        "risk_config": s.risk_config.to_dict(),
        "template_name": s.template_name,
        "template_params": s.template_params,
        "created_at": s.created_at.isoformat(),
        "updated_at": s.updated_at.isoformat(),
    }


@router.get("")
def list_strategies(
    state: str | None = None,
    market: str | None = None,
    ctx: AccessContext = Depends(get_access_context),
):
    from app.services.strategy_service import StrategyService
    svc = StrategyService()
    return [_serialize(s) for s in svc.list(ctx, state=state, market=market)]


@router.post("")
def create_strategy(
    payload: dict,
    ctx: AccessContext = Depends(get_access_context),
):
    from app.services.strategy_service import StrategyService
    svc = StrategyService()
    try:
        s = svc.create(payload, ctx)
        return _serialize(s)
    except Exception as e:
        if hasattr(e, "http_status"):
            raise HTTPException(status_code=e.http_status, detail=e.message)
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{strategy_id}")
def get_strategy(
    strategy_id: str,
    ctx: AccessContext = Depends(get_access_context),
):
    from app.services.strategy_service import StrategyService
    svc = StrategyService()
    try:
        return _serialize(svc.get(strategy_id, ctx))
    except (NotFoundError, ForbiddenError) as e:
        raise HTTPException(status_code=e.http_status, detail=e.message)


@router.patch("/{strategy_id}")
def update_strategy(
    strategy_id: str,
    payload: dict,
    ctx: AccessContext = Depends(get_access_context),
):
    from app.services.strategy_service import StrategyService
    svc = StrategyService()
    try:
        s = svc.get(strategy_id, ctx)
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
    except (NotFoundError, ForbiddenError) as e:
        raise HTTPException(status_code=e.http_status, detail=e.message)


@router.delete("/{strategy_id}")
def delete_strategy(
    strategy_id: str,
    ctx: AccessContext = Depends(get_access_context),
):
    from app.services.strategy_service import StrategyService
    svc = StrategyService()
    try:
        svc.delete(strategy_id, ctx)
        return {"deleted": True}
    except (NotFoundError, ForbiddenError, ConflictError) as e:
        raise HTTPException(status_code=e.http_status, detail=e.message)


@router.post("/{strategy_id}/transition")
def transition_strategy(
    strategy_id: str,
    payload: dict,
    ctx: AccessContext = Depends(get_access_context),
):
    from app.services.strategy_lifecycle import StrategyLifecycle
    from app.services.strategy_service import StrategyService
    svc = StrategyService()
    lifecycle = StrategyLifecycle(svc)
    try:
        s = svc.get(strategy_id, ctx)
        target = LifecycleState(payload["target_state"])
        result = lifecycle.transition(
            s, target, ctx,
            reason=payload.get("reason"),
            confirm_live=payload.get("confirm_live", False),
            confirmation_string=payload.get("confirmation_string", ""),
        )
        return _serialize(result)
    except (NotFoundError, ForbiddenError, LifecycleError, LiveDeploymentError) as e:
        raise HTTPException(status_code=e.http_status, detail=e.message)


@router.get("/{strategy_id}/versions")
def get_versions(
    strategy_id: str,
    ctx: AccessContext = Depends(get_access_context),
):
    from app.services.strategy_service import StrategyService
    svc = StrategyService()
    try:
        versions = svc.get_versions(strategy_id, ctx)
        return [{"version": v.version, "created_at": v.created_at.isoformat(),
                 "config": v.config_snapshot} for v in versions]
    except (NotFoundError, ForbiddenError) as e:
        raise HTTPException(status_code=e.http_status, detail=e.message)


@router.get("/{strategy_id}/lifecycle")
def get_lifecycle(
    strategy_id: str,
    ctx: AccessContext = Depends(get_access_context),
):
    from app.services.strategy_service import StrategyService
    svc = StrategyService()
    try:
        return svc.get_lifecycle_events(strategy_id, ctx)
    except (NotFoundError, ForbiddenError) as e:
        raise HTTPException(status_code=e.http_status, detail=e.message)
