"""User service: registration, login, session management."""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from datetime import UTC, datetime
from typing import Any

from app.core import errors
from app.core.audit import record
from app.core.auth import (
    default_session_ttl, expires_at_from_now, generate_session_token,
    hash_password, verify_password,
)
from app.core.rbac import AccessContext, public_user_payload
from app.domain.user import PublicUser, User, UserRole, UserSession, UserStatus


class UserService:
    def __init__(self, db_path: str = "trading.db") -> None:
        self._db_path = db_path
        self._lock = threading.RLock()

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(self._db_path, check_same_thread=False, isolation_level=None)

    def register(self, email: str, password: str, display_name: str | None = None,
                ctx: AccessContext | None = None) -> PublicUser:
        """Register a new user account. Anyone can call this (no auth required)."""
        email = email.strip().lower()
        if len(password) < 8:
            raise errors.ValidationError("password must be at least 8 characters")
        user_id = str(uuid.uuid4())
        now = datetime.now(UTC).isoformat()
        password_hash = hash_password(password)
        conn = self._conn()
        try:
            with self._lock:
                existing = conn.execute(
                    "SELECT id FROM users WHERE email = ?", (email,)).fetchone()
                if existing:
                    raise errors.ConflictError("email already registered")
                conn.execute(
                    "INSERT INTO users VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (user_id, email, password_hash, display_name,
                     UserRole.USER.value, UserStatus.ACTIVE.value, now, now),
                )
            record(actor=None, action="user.register", target_type="user", target_id=user_id,
                   detail={"email": email})
            return self._get_public(user_id, conn)
        finally:
            conn.close()

    def login(self, email: str, password: str) -> tuple[PublicUser, str]:
        """Authenticate and return a session token."""
        email = email.strip().lower()
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT id, email, password_hash, display_name, role, status, created_at, updated_at "
                "FROM users WHERE email = ?", (email,)).fetchone()
            if not row:
                raise errors.UnauthorizedError("invalid email or password")
            user = self._row_to_user(row)
            if not verify_password(password, user.password_hash):
                raise errors.UnauthorizedError("invalid email or password")
            if not user.is_active():
                raise errors.ForbiddenError("account is not active")
            session_id = generate_session_token()
            expires_at = expires_at_from_now().isoformat()
            now = datetime.now(UTC).isoformat()
            with self._lock:
                conn.execute(
                    "INSERT INTO user_sessions VALUES (?, ?, ?, ?, ?)",
                    (session_id, user.id, expires_at, now, None),
                )
            record(actor=user, action="user.login", target_type="user", target_id=user.id)
            return self._get_public(user.id, conn), session_id
        finally:
            conn.close()

    def logout(self, session_id: str, ctx: AccessContext) -> None:
        conn = self._conn()
        try:
            with self._lock:
                conn.execute("DELETE FROM user_sessions WHERE id = ?", (session_id,))
            record(actor=ctx.user, action="user.logout", target_type="session", target_id=session_id)
        finally:
            conn.close()

    def resolve_session(self, session_id: str) -> User | None:
        """Validate a session token and return the User, or None if invalid/expired."""
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT u.id, u.email, u.password_hash, u.display_name, u.role, u.status, "
                "u.created_at, u.updated_at "
                "FROM user_sessions s JOIN users u ON s.user_id = u.id "
                "WHERE s.id = ? AND s.expires_at > ?",
                (session_id, datetime.now(UTC).isoformat()),
            ).fetchone()
            if not row:
                return None
            # Touch last_used_at
            conn.execute(
                "UPDATE user_sessions SET last_used_at = ? WHERE id = ?",
                (datetime.now(UTC).isoformat(), session_id),
            )
            return self._row_to_user(row)
        finally:
            conn.close()

    def get_me(self, ctx: AccessContext) -> PublicUser:
        return public_user_payload(ctx.user)

    def list_users(self, ctx: AccessContext) -> list[PublicUser]:
        ctx.require_admin()
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT id, email, display_name, role, status, created_at FROM users "
                "WHERE status != ? ORDER BY created_at DESC",
                (UserStatus.DELETED.value,)).fetchall()
            return [PublicUser(
                id=r[0], email=r[1], display_name=r[2],
                role=UserRole(r[3]), status=UserStatus(r[4]),
                created_at=datetime.fromisoformat(r[5])) for r in rows]
        finally:
            conn.close()

    def suspend_user(self, user_id: str, ctx: AccessContext) -> PublicUser:
        ctx.require_admin()
        conn = self._conn()
        try:
            with self._lock:
                conn.execute("UPDATE users SET status = ?, updated_at = ? WHERE id = ?",
                             (UserStatus.SUSPENDED.value, datetime.now(UTC).isoformat(), user_id))
            record(actor=ctx.user, action="user.suspend", target_type="user", target_id=user_id)
            return self._get_public(user_id, conn)
        finally:
            conn.close()

    def _get_public(self, user_id: str, conn: sqlite3.Connection) -> PublicUser:
        row = conn.execute(
            "SELECT id, email, display_name, role, status, created_at FROM users WHERE id = ?",
            (user_id,)).fetchone()
        if not row:
            raise errors.NotFoundError("user not found")
        return PublicUser(
            id=row[0], email=row[1], display_name=row[2],
            role=UserRole(row[3]), status=UserStatus(row[4]),
            created_at=datetime.fromisoformat(row[5]))

    def _row_to_user(self, row: tuple) -> User:
        return User(
            id=row[0], email=row[1], password_hash=row[2], display_name=row[3],
            role=UserRole(row[4]), status=UserStatus(row[5]),
            created_at=datetime.fromisoformat(row[6]) if row[6] else datetime.now(UTC),
            updated_at=datetime.fromisoformat(row[7]) if row[7] else datetime.now(UTC),
        )
