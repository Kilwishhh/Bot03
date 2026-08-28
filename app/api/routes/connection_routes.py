"""Connection routes: /connections/* — store/test/delete exchange credentials."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies import get_access_context
from app.core.errors import NotFoundError, ValidationError
from app.core.rbac import AccessContext

router = APIRouter(prefix="/connections", tags=["connections"])


@router.get("")
def list_connections(
    venue: str | None = None,
    ctx: AccessContext = Depends(get_access_context),
):
    from app.services.connection_service import ConnectionService
    svc = ConnectionService()
    return [c.to_dict() for c in svc.list(ctx, venue=venue)]


@router.post("")
def create_connection(
    payload: dict,
    ctx: AccessContext = Depends(get_access_context),
):
    from app.services.connection_service import ConnectionService
    svc = ConnectionService()
    try:
        c = svc.create(payload, ctx)
        return c.to_dict()
    except Exception as e:
        if hasattr(e, "http_status"):
            raise HTTPException(status_code=e.http_status, detail=e.message)
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{conn_id}")
def get_connection(
    conn_id: str,
    ctx: AccessContext = Depends(get_access_context),
):
    from app.services.connection_service import ConnectionService
    svc = ConnectionService()
    try:
        return svc.get(conn_id, ctx).to_dict()
    except (NotFoundError, ValidationError) as e:
        raise HTTPException(status_code=e.http_status, detail=e.message)


@router.delete("/{conn_id}")
def delete_connection(
    conn_id: str,
    ctx: AccessContext = Depends(get_access_context),
):
    from app.services.connection_service import ConnectionService
    svc = ConnectionService()
    try:
        svc.delete(conn_id, ctx)
        return {"deleted": True}
    except (NotFoundError, ValidationError) as e:
        raise HTTPException(status_code=e.http_status, detail=e.message)


@router.post("/{conn_id}/test")
def test_connection(
    conn_id: str,
    ctx: AccessContext = Depends(get_access_context),
):
    from app.services.connection_service import ConnectionService
    svc = ConnectionService()
    try:
        return svc.test_connection(conn_id, ctx)
    except (NotFoundError, ValidationError) as e:
        raise HTTPException(status_code=e.http_status, detail=e.message)
