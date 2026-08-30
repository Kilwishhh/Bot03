"""Connection service: encrypted storage and retrieval of exchange credentials."""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from datetime import UTC, datetime
from typing import Any

from app.core import errors
from app.core.audit import record
from app.core.crypto import encrypt
from app.core.rbac import AccessContext
from app.domain.connection import (
    ConnectionStatus,
    ConnectionVenue,
    ExchangeConnection,
)


class ConnectionService:
    def __init__(self, db_path: str = "trading.db") -> None:
        self._db_path = db_path
        self._lock = threading.RLock()

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(self._db_path, check_same_thread=False, isolation_level=None)

    def create(self, payload: dict[str, Any], ctx: AccessContext) -> ExchangeConnection:
        """Store a new exchange connection with encrypted secrets."""
        ctx.require_active()
        try:
            venue = ConnectionVenue(payload["venue"])
        except (KeyError, ValueError):
            raise errors.ValidationError("valid venue required (binance, hyperliquid, walletconnect)")

        conn_id = str(uuid.uuid4())
        now = datetime.now(UTC).isoformat()
        api_key_enc = encrypt(payload.get("api_key", ""))
        api_secret_enc = encrypt(payload["api_secret"]) if payload.get("api_secret") else None

        conn = self._conn()
        try:
            with self._lock:
                conn.execute(
                    "INSERT INTO exchange_connections VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        conn_id, ctx.user.id, venue.value, payload.get("label"),
                        api_key_enc, api_secret_enc,
                        payload.get("wallet_address"),
                        json.dumps(payload.get("permissions", {"read": True, "trade": False, "withdraw": False})),
                        ConnectionStatus.CONNECTED.value, now, now,
                    ),
                )
            record(actor=ctx.user, action="connection.create",
                   target_type="exchange_connection", target_id=conn_id,
                   detail={"venue": venue.value, "label": payload.get("label")})
            return self.get(conn_id, ctx)
        finally:
            conn.close()

    def get(self, conn_id: str, ctx: AccessContext) -> ExchangeConnection:
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT id, user_id, venue, label, api_key_enc, api_secret_enc, "
                "wallet_address, permissions, status, created_at, updated_at "
                "FROM exchange_connections WHERE id = ?",
                (conn_id,),
            ).fetchone()
            if not row:
                raise errors.NotFoundError("connection not found")
            c = self._row_to_conn(row)
            ctx.require_owner(c.user_id)
            return c
        finally:
            conn.close()

    def list(self, ctx: AccessContext, venue: str | None = None) -> list[ExchangeConnection]:
        conn = self._conn()
        try:
            query = "SELECT * FROM exchange_connections WHERE user_id = ?"
            params: list[Any] = [ctx.user.id]
            if venue:
                query += " AND venue = ?"
                params.append(venue)
            query += " ORDER BY created_at DESC"
            rows = conn.execute(query, params).fetchall()
            return [self._row_to_conn(r) for r in rows]
        finally:
            conn.close()

    def delete(self, conn_id: str, ctx: AccessContext) -> None:
        conn = self._conn()
        try:
            c = self.get(conn_id, ctx)
            with self._lock:
                conn.execute("DELETE FROM exchange_connections WHERE id = ?", (conn_id,))
            record(actor=ctx.user, action="connection.delete",
                   target_type="exchange_connection", target_id=conn_id)
        finally:
            conn.close()

    def test_connection(self, conn_id: str, ctx: AccessContext) -> dict[str, Any]:
        """Placeholder: tests connectivity to the exchange. Returns mock for now."""
        c = self.get(conn_id, ctx)
        return {"venue": c.venue.value if hasattr(c.venue, "value") else str(c.venue),
                "status": "connected", "tested_at": datetime.now(UTC).isoformat()}

    def _row_to_conn(self, row: tuple) -> ExchangeConnection:
        return ExchangeConnection(
            id=row[0], user_id=row[1],
            venue=ConnectionVenue(row[2]), label=row[3] or None,
            api_key_enc=row[4] or b"", api_secret_enc=row[5] or None,
            wallet_address=row[6] or None,
            permissions=json.loads(row[7]) if row[7] else {},
            status=ConnectionStatus(row[8]) if row[8] else ConnectionStatus.DISCONNECTED,
            created_at=datetime.fromisoformat(row[9]) if row[9] else datetime.now(UTC),
            updated_at=datetime.fromisoformat(row[10]) if row[10] else datetime.now(UTC),
        )
