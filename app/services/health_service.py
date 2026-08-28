"""Health service: aggregates 8 service checks into a single /health/system response."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from typing import Any

from app.core.rbac import AccessContext


class HealthService:
    def __init__(self, db_path: str = "trading.db") -> None:
        self._db_path = db_path

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(self._db_path, check_same_thread=False, isolation_level=None)

    def check_all(self, ctx: AccessContext) -> dict[str, Any]:
        checks: list[dict] = []
        healthy = True

        for name, result in [
            ("database",    self._check_db()),
            ("users",       self._check_table("users", "user records")),
            ("strategies",  self._check_table("strategies", "strategy records")),
            ("signals",     self._check_table("signals", "signal records")),
            ("automation",  self._check_table("automation_rules", "automation rules")),
            ("publications", self._check_table("publications", "publication records")),
            ("audit_log",   self._check_table("audit_log", "audit entries")),
            ("schema_migrations", self._check_table("schema_migrations", "applied migrations")),
        ]:
            checks.append({"service": name, **result})
            if result["status"] != "ok":
                healthy = False

        return {
            "healthy": healthy,
            "checked_at": datetime.now(UTC).isoformat(),
            "checks": checks,
        }

    def _check_db(self) -> dict[str, Any]:
        try:
            conn = self._conn()
            conn.execute("SELECT 1").fetchone()
            conn.close()
            return {"status": "ok", "message": "connected"}
        except Exception as exc:
            return {"status": "error", "message": str(exc)}

    def _check_table(self, table: str, description: str) -> dict[str, Any]:
        try:
            conn = self._conn()
            count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            conn.close()
            return {"status": "ok", "message": f"{count} {description}"}
        except sqlite3.OperationalError as exc:
            return {"status": "missing", "message": f"table not found: {exc}"}
        except Exception as exc:
            return {"status": "error", "message": str(exc)}
