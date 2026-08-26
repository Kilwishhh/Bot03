from fastapi import Header, HTTPException
import secrets
from app.config import Settings


def _check_bearer(authorization: str | None, expected_token: str) -> None:
    if not authorization:
        raise HTTPException(status_code=401, detail="missing authorization header")
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="malformed authorization header")
    if not secrets.compare_digest(parts[1], expected_token):
        raise HTTPException(status_code=401, detail="invalid token")


def require_control_token(authorization: str | None = Header(default=None, alias="Authorization")) -> None:
    """Gate remote control endpoints. Only enforced when remote control is enabled."""
    settings = Settings()
    if not settings.enable_remote_control:
        raise HTTPException(status_code=403, detail="remote control disabled")
    token = settings.control_api_token
    if not token:
        raise HTTPException(status_code=403, detail="remote control token not configured")
    _check_bearer(authorization, token)


def require_admin_token(authorization: str | None = Header(default=None, alias="Authorization")) -> None:
    """Gate admin endpoints. If no admin token is configured, all admin requests are rejected."""
    token = Settings().admin_api_token
    if not token:
        raise HTTPException(
            status_code=403,
            detail="admin endpoints disabled; set ADMIN_API_TOKEN in your environment to enable",
        )
    _check_bearer(authorization, token)