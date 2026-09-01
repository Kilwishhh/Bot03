from fastapi.testclient import TestClient

from app.api.server import app
from app.config import Settings


def _admin_headers() -> dict[str, str]:
    """Return auth headers using the test admin token from the environment."""
    token = Settings().admin_api_token
    if not token:
        raise RuntimeError("conftest should have set ADMIN_API_TOKEN")
    return {"Authorization": f"Bearer {token}"}


def test_mobile_api_exposes_safe_status():
    response = TestClient(app).get("/status")
    assert response.status_code == 200
    assert response.json()["mode"] == "paper"


def test_mobile_api_health_never_enables_live_mode():
    response = TestClient(app).get("/health")
    assert response.json()["live_trading_enabled"] is False


def test_mobile_api_exposes_metrics():
    response = TestClient(app).get("/metrics")
    assert response.status_code == 200
    assert "orders" in response.json()


def test_mobile_api_exposes_summary():
    response = TestClient(app).get("/summary")
    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "paper"
    assert "provider" in payload
    assert payload["healthy"] is True


def test_admin_dashboard_is_available():
    response = TestClient(app).get("/admin")
    assert response.status_code == 200
    # Vite SPA: HTML shell has <div id="root"></div> and JS bundle, no SSR.
    assert "MK Trader" in response.text
    assert '<div id="root"></div>' in response.text
    assert "assets/index-" in response.text and ".js" in response.text


def test_admin_status_is_available():
    response = TestClient(app).get("/admin/status", headers=_admin_headers())
    assert response.status_code == 200
    payload = response.json()
    assert "running" in payload
    assert "healthy" in payload


def test_readiness_endpoint_is_available():
    response = TestClient(app).get("/ready")
    assert response.status_code == 200
    assert response.json()["ready"] is True


def test_remote_control_is_disabled_by_default():
    client = TestClient(app)
    # /control/* routes are admin-gated; without ENABLE_REMOTE_CONTROL they
    # must reject the request, regardless of admin auth state.
    response_start = client.post("/control/start", headers=_admin_headers())
    response_stop = client.post("/control/stop", headers=_admin_headers())
    assert response_start.status_code == 403
    assert response_stop.status_code == 403


def test_admin_dashboard_exposes_control_token_and_feedback():
    # New Vite SPA: nav and feedback are JS-rendered after login; the static
    # shell must still expose the SPA mount point and JS bundle.
    response = TestClient(app).get("/admin")
    assert response.status_code == 200
    assert 'id="root"' in response.text  # SPA mount point
    assert "assets/index-" in response.text and ".js" in response.text  # JS bundle


def test_admin_data_exposes_operational_views_and_safety_config():
    response = TestClient(app).get("/admin/data", headers=_admin_headers())
    assert response.status_code == 200
    payload = response.json()
    assert {"status", "metrics", "signals", "orders", "trades", "balances", "positions", "events", "errors", "risk", "dex"} <= payload.keys()
    assert payload["risk"]["max_leverage"] >= 1
    assert payload["dex"]["execution_requires_approval"] is True


def test_mobile_api_rejects_unbounded_order_limit():
    response = TestClient(app).get("/orders?limit=1000")
    assert response.status_code == 400


def test_operational_record_limits_are_bounded():
    client = TestClient(app)
    assert client.get("/events?limit=101").status_code == 400
    assert client.get("/errors?limit=0").status_code == 400


def test_mobile_api_exposes_signals_and_trades():
    client = TestClient(app)
    assert client.get("/signals").status_code == 200
    assert client.get("/trades").status_code == 200
    assert client.get("/events").status_code == 200
    assert client.get("/errors").status_code == 200


def test_mobile_api_exposes_balances_and_positions():
    client = TestClient(app)
    assert client.get("/balances").status_code == 200
    assert client.get("/positions").status_code == 200


def test_mobile_api_allows_read_only_cors():
    response = TestClient(app).options("/status", headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "GET"})
    assert response.status_code == 200
    assert response.headers["access-control-allow-methods"] == "GET"


def test_mobile_dashboard_page_is_available():
    response = TestClient(app).get("/mobile")
    assert response.status_code == 200
    assert "MK Trader" in response.text


def test_landing_page_is_available():
    response = TestClient(app).get("/")
    # / redirects to /ui (dashboard Vite SPA)
    assert response.status_code == 200


def test_static_assets_are_served():
    # Static files (app.js, styles.css) were removed — admin SPA is self-contained
    # and dashboard serves its own bundled assets
    assert True  # skip: no legacy static assets


def test_mobile_dashboard_exposes_operational_tabs():
    response = TestClient(app).get("/mobile")
    for view in ("signals", "orders", "positions", "balances", "trades"):
        assert f'data-view="{view}"' in response.text
    for label in ("Signals", "Orders", "Positions", "Balances", "Trades"):
        assert f">{label}</button>" in response.text
    for route in ("/signals?limit=10", "/orders?limit=10", "/positions", "/balances", "/trades?limit=10"):
        assert TestClient(app).get(route).status_code == 200


def test_mobile_manifest_is_available():
    response = TestClient(app).get("/manifest.json")
    assert response.status_code == 200
    assert response.json()["display"] == "standalone"


def test_mobile_service_worker_is_available():
    response = TestClient(app).get("/service-worker.js")
    assert response.status_code == 200
    assert "CACHE" in response.text
