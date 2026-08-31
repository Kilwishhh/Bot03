"""Phase 4 — HealthService and /health/system endpoint tests."""

import pytest
from fastapi.testclient import TestClient

from app.api.server import app
from app.services.health_service import HealthService


@pytest.fixture
def client():
    return TestClient(app, raise_server_exceptions=False)


class TestHealthService:
    def test_check_all_returns_structure(self, tmp_path):
        """check_all returns healthy + checked_at + checks list."""
        db = str(tmp_path / "hs.db")
        svc = HealthService(db)
        result = svc.check_all(ctx=None)
        assert "healthy" in result
        assert "checked_at" in result
        assert "checks" in result
        assert isinstance(result["checks"], list)

    def test_check_all_reports_missing_tables(self, tmp_path):
        """Tables that don't exist are reported as 'missing'."""
        db = str(tmp_path / "hs_empty.db")
        svc = HealthService(db)
        result = svc.check_all(ctx=None)
        assert result["healthy"] is False
        table_names = {c["service"] for c in result["checks"]}
        for name in ("users", "strategies", "signals", "automation", "publications"):
            svc_check = next(c for c in result["checks"] if c["service"] == name)
            assert svc_check["status"] == "missing", f"{name} should be missing"

    def test_check_all_returns_ok_when_tables_exist(self, tmp_path):
        """When all tables exist, health is True."""
        db = str(tmp_path / "hs_ok.db")
        import sqlite3
        conn = sqlite3.connect(db)
        for ddl in (
            "CREATE TABLE users (id TEXT PRIMARY KEY)",
            "CREATE TABLE strategies (id TEXT PRIMARY KEY)",
            "CREATE TABLE signals (id TEXT)",
            "CREATE TABLE automation_rules (id TEXT)",
            "CREATE TABLE publications (id TEXT)",
            "CREATE TABLE audit_log (id TEXT)",
            "CREATE TABLE schema_migrations (name TEXT PRIMARY KEY)",
        ):
            conn.execute(ddl)
        conn.close()

        svc = HealthService(db)
        result = svc.check_all(ctx=None)
        assert result["healthy"] is True
        statuses = {c["service"]: c["status"] for c in result["checks"]}
        assert all(s == "ok" for s in statuses.values()), statuses


class TestHealthSystemEndpoint:
    def test_health_system_returns_200(self, client, monkeypatch):
        """GET /health/system responds 200 with admin token."""
        monkeypatch.setenv("ADMIN_API_TOKEN", "test-admin-secret-token-12345")
        resp = client.get("/health/system", headers={"X-Admin-Token": "test-admin-secret-token-12345"})
        assert resp.status_code == 200, f"got {resp.status_code}: {resp.text[:200]}"

    def test_health_system_returns_healthy_and_checks(self, client, monkeypatch):
        """Response includes healthy bool and checks list."""
        monkeypatch.setenv("ADMIN_API_TOKEN", "test-admin-secret-token-12345")
        resp = client.get("/health/system", headers={"X-Admin-Token": "test-admin-secret-token-12345"})
        data = resp.json()
        assert "healthy" in data
        assert "checks" in data
        assert isinstance(data["checks"], list)

    def test_health_system_includes_all_services(self, client, monkeypatch):
        """All 8 services are present in the checks list."""
        monkeypatch.setenv("ADMIN_API_TOKEN", "test-admin-secret-token-12345")
        resp = client.get("/health/system", headers={"X-Admin-Token": "test-admin-secret-token-12345"})
        data = resp.json()
        names = {c["service"] for c in data["checks"]}
        expected = {
            "database", "users", "strategies", "signals",
            "automation", "publications", "audit_log", "schema_migrations",
        }
        assert expected.issubset(names), f"Missing: {expected - names}"
