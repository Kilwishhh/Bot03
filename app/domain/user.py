"""User domain entities."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum


class UserRole(StrEnum):
    USER = "user"
    ADMIN = "admin"
    SYSTEM = "system"


class UserStatus(StrEnum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    DELETED = "deleted"


@dataclass
class User:
    id: str
    email: str
    password_hash: str
    display_name: str | None = None
    role: UserRole = UserRole.USER
    status: UserStatus = UserStatus.ACTIVE
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def is_active(self) -> bool:
        return self.status == UserStatus.ACTIVE

    def is_admin(self) -> bool:
        return self.role == UserRole.ADMIN

    def is_system(self) -> bool:
        return self.role == UserRole.SYSTEM


@dataclass
class UserSession:
    id: str
    user_id: str
    expires_at: datetime
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    last_used_at: datetime | None = None

    def is_expired(self) -> bool:
        return datetime.now(UTC) > self.expires_at


@dataclass
class PublicUser:
    """Safe to return via API — never includes password_hash."""
    id: str
    email: str
    display_name: str | None
    role: UserRole
    status: UserStatus
    created_at: datetime

    @classmethod
    def from_user(cls, user: User) -> "PublicUser":
        return cls(
            id=user.id,
            email=user.email,
            display_name=user.display_name,
            role=user.role,
            status=user.status,
            created_at=user.created_at,
        )
