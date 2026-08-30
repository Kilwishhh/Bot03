"""FastAPI dependency: resolve Bearer token → AccessContext.

Tries in order:
1. Bearer token from Authorization header (new user sessions)
2. X-Admin-Token header (legacy admin token)
3. X-Control-Token header (legacy control token)
4. Raises 401 if nothing valid.
"""

from __future__ import annotations

import os

from fastapi import Header, HTTPException, status

from app.domain.user import User, UserRole, UserStatus


def _make_system_user(role: str = "system") -> User:
    """Return a system-user context for legacy token auth."""
    from datetime import UTC, datetime
    return User(
        id="system", email="system@legacy", password_hash="!disabled",
        display_name="System", role=UserRole(role),
        status=UserStatus.ACTIVE,
        created_at=datetime.now(UTC), updated_at=datetime.now(UTC),
    )


def _make_admin_user() -> User:
    return _make_system_user("admin")


async def get_access_context(
    authorization: str | None = Header(None, alias="Authorization"),
    x_admin_token: str | None = Header(None, alias="X-Admin-Token"),
    x_control_token: str | None = Header(None, alias="X-Control-Token"),
) -> AccessContext:
    """Resolve the current request's identity into an AccessContext."""
    from app.core.rbac import AccessContext
    from app.services.user_service import UserService

    # 1. Bearer session token
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:]
        if not token:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                                detail="invalid token")
        svc = UserService()
        user = svc.resolve_session(token)
        if user:
            return AccessContext(user=user)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="session expired or invalid")

    # 2. Legacy X-Admin-Token
    if x_admin_token:
        expected = os.environ.get("ADMIN_API_TOKEN", "")
        if x_admin_token == expected and expected:
            return AccessContext(user=_make_admin_user())
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="invalid admin token")

    # 3. Legacy X-Control-Token
    if x_control_token:
        expected = os.environ.get("CONTROL_API_TOKEN", "")
        if x_control_token == expected and expected:
            return AccessContext(user=_make_system_user("user"))
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="invalid control token")

    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="authentication required")


async def get_optional_context(
    authorization: str | None = Header(None, alias="Authorization"),
    x_admin_token: str | None = Header(None, alias="X-Admin-Token"),
    x_control_token: str | None = Header(None, alias="X-Control-Token"),
) -> AccessContext | None:
    """Like get_access_context but returns None instead of 401 when unauthenticated."""
    try:
        return await get_access_context(authorization, x_admin_token, x_control_token)
    except HTTPException:
        return None
