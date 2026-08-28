"""Role-based access control helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.core.errors import ForbiddenError
from app.domain.user import User, UserRole


@dataclass
class AccessContext:
    """A snapshot of who is making the request and what they can see/do."""
    user: User

    @property
    def user_id(self) -> str:
        return self.user.id

    @property
    def role(self) -> UserRole:
        return self.user.role

    def is_admin(self) -> bool:
        return self.user.is_admin()

    def is_system(self) -> bool:
        return self.user.is_system()

    def require_active(self) -> None:
        if not self.user.is_active():
            raise ForbiddenError("user is not active")

    def require_admin(self) -> None:
        if not self.user.is_admin():
            raise ForbiddenError("admin role required")

    def require_owner(self, owner_user_id: str) -> None:
        """Succeeds for the owner or for admin. Raises Forbidden for anyone else."""
        if self.user.is_admin():
            return
        if self.user.id != owner_user_id:
            # Use NotFound semantics via Forbidden; API layer will translate
            raise ForbiddenError("not authorized for this resource")

    def scoped_user_id(self, owner_user_id: str) -> str:
        """Return the user_id to filter by. Admins see the owner's data; non-admins see only their own."""
        if self.user.is_admin():
            return owner_user_id
        return self.user.id


def public_user_payload(user: User) -> dict[str, Any]:
    """Return a safe JSON-serializable dict for an API response."""
    return {
        "id": user.id,
        "email": user.email,
        "display_name": user.display_name,
        "role": user.role.value if hasattr(user.role, "value") else str(user.role),
        "status": user.status.value if hasattr(user.status, "value") else str(user.status),
        "created_at": user.created_at.isoformat() if hasattr(user.created_at, "isoformat") else user.created_at,
    }
