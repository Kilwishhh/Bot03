"""Health route: /health/system — 8-service aggregate."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.dependencies import get_access_context
from app.core.rbac import AccessContext

router = APIRouter(tags=["health"])


@router.get("/health/system")
def system_health(ctx: AccessContext = Depends(get_access_context)):
    from app.services.health_service import HealthService
    return HealthService().check_all(ctx)
