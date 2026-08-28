"""User auth routes: /auth/* + /me."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.errors import (
    ConflictError, ForbiddenError, NotFoundError, UnauthorizedError,
)
from app.core.rbac import AccessContext
from app.api.dependencies import get_access_context

router = APIRouter(tags=["auth"])


@router.post("/auth/register")
def register(payload: dict):
    from app.services.user_service import UserService
    svc = UserService()
    try:
        user = svc.register(
            email=payload.get("email", ""),
            password=payload.get("password", ""),
            display_name=payload.get("display_name"),
        )
        return {
            "id": user.id, "email": user.email,
            "display_name": user.display_name,
            "role": str(user.role), "status": str(user.status),
            "created_at": user.created_at.isoformat(),
        }
    except (ValueError, ConflictError) as e:
        raise HTTPException(status_code=409 if isinstance(e, ConflictError) else 400,
                            detail=str(e.message if hasattr(e, "message") else e))


@router.post("/auth/login")
def login(payload: dict):
    from app.services.user_service import UserService
    svc = UserService()
    try:
        user, token = svc.login(
            email=payload.get("email", ""),
            password=payload.get("password", ""),
        )
        return {
            "token": token,
            "user": {
                "id": user.id, "email": user.email,
                "display_name": user.display_name,
                "role": str(user.role), "status": str(user.status),
            },
        }
    except UnauthorizedError as e:
        raise HTTPException(status_code=401, detail=e.message)
    except ForbiddenError as e:
        raise HTTPException(status_code=403, detail=e.message)


@router.post("/auth/logout")
def logout(payload: dict, ctx: AccessContext = Depends(get_access_context)):
    from app.services.user_service import UserService
    svc = UserService()
    token = payload.get("token", "")
    if not token:
        raise HTTPException(status_code=400, detail="token required")
    svc.logout(token, ctx)
    return {"logged_out": True}


@router.get("/me")
def me(ctx: AccessContext = Depends(get_access_context)):
    return {
        "id": ctx.user.id, "email": ctx.user.email,
        "display_name": ctx.user.display_name,
        "role": str(ctx.user.role), "status": str(ctx.user.status),
        "is_admin": ctx.is_admin(),
    }
