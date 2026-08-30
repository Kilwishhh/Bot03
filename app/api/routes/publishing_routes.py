"""Publishing routes: /publishing/* — config + Telegram/Square posting."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.dependencies import get_access_context
from app.core.rbac import AccessContext

router = APIRouter(prefix="/publishing", tags=["publishing"])


@router.get("/config")
def get_config(ctx: AccessContext = Depends(get_access_context)):
    from app.services.publishing_service import PublishingService
    return PublishingService().get_config(ctx)


@router.put("/config")
def update_config(
    payload: dict,
    ctx: AccessContext = Depends(get_access_context),
):
    from app.services.publishing_service import PublishingService
    return PublishingService().update_config(payload, ctx)


@router.post("/telegram")
def publish_telegram(
    payload: dict,
    ctx: AccessContext = Depends(get_access_context),
):
    from app.services.publishing_service import PublishingService
    return PublishingService().publish_telegram(
        signal_id=payload.get("signal_id"),
        ctx=ctx,
        template=payload.get("template", "default"),
    )


@router.post("/square")
def publish_square(
    payload: dict,
    ctx: AccessContext = Depends(get_access_context),
):
    from app.services.publishing_service import PublishingService
    return PublishingService().publish_square(
        signal_id=payload.get("signal_id"),
        ctx=ctx,
        template=payload.get("template", "default"),
    )


@router.get("/publications")
def list_publications(
    limit: int = 50,
    ctx: AccessContext = Depends(get_access_context),
):
    from app.services.publishing_service import PublishingService
    return PublishingService().list_publications(ctx, limit=min(limit, 200))
