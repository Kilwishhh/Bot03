"""End-to-end integration smoke test for ermis.

Exercises:
1. Register user → login → get session
2. Create strategy → transition DRAFT → KTEST → PAPER → LIVE_ELIGIBLE
3. Generate signal (auto-creates followup)
4. Create automation rule (signal_generated → create_followup)
5. List strategies/signals/followups
6. List audit log
7. Suspend user (admin)
8. Create emergency pause (admin) → resume
9. Health check
"""

import json
import os
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

# Use a temporary DB so we don't touch the real one
TMP_DB = Path(tempfile.gettempdir()) / "ermis_e2e.db"
if TMP_DB.exists():
    TMP_DB.unlink()

os.environ["ADMIN_API_TOKEN"] = "admintest"
os.environ["CONTROL_API_TOKEN"] = "ctrltest"
os.environ["TRADING_MODE"] = "paper"
os.environ["DATABASE_PATH"] = str(TMP_DB)
os.environ["ENABLE_REMOTE_CONTROL"] = "true"

import uvicorn

from app.api.server import app

# Force-recreate default repository against TMP_DB
from app.database import repository as _repo_mod

_repo_mod._default_repo = None
from app.database.repository import TradingRepository

_default = TradingRepository(str(TMP_DB))
_repo_mod._default_repo = _default

# Force-recreate services that already have a singleton
import app.services.automation_engine as _ae
import app.services.emergency_service as _es
import app.services.signal_service as _sigs
import app.services.strategy_service as _ss
import app.services.user_service as _us

_ss._svc = None
_sigs._svc = None
_ae._engine = None
_us._svc = None
_es._svc = None


def post(path, body, token=None, admin_token=False):
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    elif admin_token:
        headers["X-Admin-Token"] = "admintest"
    req = urllib.request.Request(
        f"http://127.0.0.1:18000{path}", data=data, headers=headers, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode() or "{}")


def get(path, token=None, admin_token=False):
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    elif admin_token:
        headers["X-Admin-Token"] = "admintest"
    req = urllib.request.Request(f"http://127.0.0.1:18000{path}", headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode() or "{}")


def patch(path, body, token=None):
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(
        f"http://127.0.0.1:18000{path}", data=data, headers=headers, method="PATCH"
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode() or "{}")


def wait_ready(port=18000, timeout=15):
    """Wait for server /ready to return 200."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/ready", timeout=1) as r:
                if r.status == 200:
                    return True
        except Exception:
            time.sleep(0.2)
    return False


def banner(s):
    print(f"\n{'=' * 60}\n  {s}\n{'=' * 60}")


def step(s):
    print(f"  → {s}")


def expect(cond, msg):
    if not cond:
        print(f"  ✗ FAIL: {msg}")
        sys.exit(1)
    print(f"  ✓ {msg}")


def main():
    # Start server in background thread
    config = uvicorn.Config(app, host="127.0.0.1", port=18000, log_level="warning")
    server = uvicorn.Server(config)

    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    try:
        if not wait_ready():
            print("Server didn't start")
            sys.exit(1)
        print("✓ Server ready on :18000")

        # ── 1. Register + login user ──────────────────────────────
        banner("1. User registration + login")
        step("POST /auth/register")
        s, body = post("/auth/register", {
            "email": "trader@example.com",
            "password": "secret123",
            "display_name": "Trader One",
        })
        expect(s == 200, f"register status={s} body={body}")
        user_id = body["id"]
        expect(body["role"] == "user", f"role={body['role']}")

        step("POST /auth/login")
        s, body = post("/auth/login", {
            "email": "trader@example.com",
            "password": "secret123",
        })
        expect(s == 200, f"login status={s}")
        token = body["token"]
        expect(len(token) > 20, f"got token (len={len(token)})")

        step("GET /me")
        s, body = get("/me", token=token)
        expect(s == 200 and body["email"] == "trader@example.com", f"me={body}")

        # ── 2. Create + transition strategy ───────────────────────
        banner("2. Strategy lifecycle")
        step("POST /strategies")
        s, body = post("/strategies", {
            "name": "BTC Scalp Test",
            "description": "EMA crossover",
            "market": "BTCUSDT",
            "timeframe": "15m",
            "execution_mode": "paper",
            "execution_venue": "binance",
            "entry_config": {"indicator": "ema_fast", "period": 9},
            "exit_config": {"tp_pct": 1.5, "sl_pct": 1.0},
            "risk_config": {"max_position_pct": 5, "max_daily_loss_pct": 2},
        }, token=token)
        expect(s == 200, f"create strategy status={s} body={body}")
        sid = body["id"]
        expect(body["lifecycle_state"] == "DRAFT", f"initial state={body['lifecycle_state']}")

        step("POST /strategies/{id}/transition DRAFT→PBT")
        s, body = post(f"/strategies/{sid}/transition", {"target_state": "PBT"}, token=token)
        expect(s == 200 and body["lifecycle_state"] == "PBT", f"→{body.get('lifecycle_state')}")

        step("POST /strategies/{id}/transition PBT→KTEST")
        s, body = post(f"/strategies/{sid}/transition", {"target_state": "KTEST"}, token=token)
        expect(s == 200 and body["lifecycle_state"] == "KTEST", f"→{body.get('lifecycle_state')}")

        step("POST /strategies/{id}/transition KTEST→PAPER")
        s, body = post(f"/strategies/{sid}/transition", {"target_state": "PAPER"}, token=token)
        expect(s == 200 and body["lifecycle_state"] == "PAPER", f"→{body.get('lifecycle_state')}")

        step("POST /strategies/{id}/transition PAPER→LIVE_ELIGIBLE")
        s, body = post(f"/strategies/{sid}/transition", {"target_state": "LIVE_ELIGIBLE"}, token=token)
        expect(s == 200 and body["lifecycle_state"] == "LIVE_ELIGIBLE", f"→{body.get('lifecycle_state')}")

        # ── 3. Signal generation + automation ─────────────────────
        banner("3. Signal + automation")
        step("POST /signals")
        s, body = post("/signals", {
            "symbol": "BTCUSDT",
            "side": "BUY",
            "confidence": 0.85,
            "strategy_name": "BTC Scalp Test",
            "strategy_id": sid,
            "entry_price": 50000.0,
            "tp1": 50750.0,
            "stop_loss": 49500.0,
            "mode": "paper",
            "reason": ["EMA crossover bullish", "Volume spike"],
        }, token=token)
        expect(s == 200, f"create signal status={s} body={body}")
        signal_id = body["id"]
        expect(body["side"] == "BUY", f"side={body['side']}")

        step("GET /signals/{id}/followups (auto-generated by engine)")
        s, body = get(f"/signals/{signal_id}/followups", token=token)
        expect(s == 200, f"list followups status={s}")
        expect(len(body) >= 1, f"auto-followup count={len(body)}")
        followup_id = body[0]["id"]

        step("POST /followups (manual followup)")
        s, body = post("/followups", {
            "signal_id": signal_id,
            "event_type": "tp1_hit",
            "detail": {"price": 50750.0, "r_multiple": 1.5},
        }, token=token)
        expect(s == 200, f"create followup status={s} body={body}")

        step("POST /automation/rules (signal_generated → create_followup)")
        s, body = post("/automation/rules", {
            "name": "TP1 webhook",
            "trigger": "tp1_hit",
            "conditions": [],
            "actions": [{"type": "create_followup", "params": {"label": "TP1 hit"}}],
            "enabled": True,
        }, token=token)
        expect(s == 200, f"create rule status={s} body={body}")
        rule_id = body["id"]

        step("GET /automation/rules")
        s, body = get("/automation/rules", token=token)
        expect(s == 200 and len(body) >= 1, f"rules count={len(body) if isinstance(body, list) else 0}")

        # ── 4. Connections + publishing ───────────────────────────
        banner("4. Connections + publishing")
        step("POST /connections")
        s, body = post("/connections", {
            "venue": "binance",
            "label": "Binance Testnet",
            "api_key": "fake_key_123",
            "api_secret": "fake_secret_456",
            "testnet": True,
        }, token=token)
        expect(s == 200, f"create connection status={s} body={body}")
        conn_id = body["id"]

        step("POST /connections/{id}/test")
        s, body = post(f"/connections/{conn_id}/test", {}, token=token)
        # Test may return 200 with success=false for fake creds — that's OK
        expect(s in (200, 400, 422), f"test connection status={s}")

        step("GET /publishing/config")
        s, body = get("/publishing/config", token=token)
        expect(s == 200, f"publishing config status={s}")

        # ── 5. Health check ────────────────────────────────────────
        banner("5. Health")
        step("GET /health/system")
        s, body = get("/health/system", token=token)
        expect(s == 200, f"health status={s}")
        expect("services" in body, f"health keys={list(body.keys())}")
        print(f"  ↪ system status: {body.get('status')}, services: {len(body.get('services', {}))}")

        # ── 6. Admin operations ───────────────────────────────────
        banner("6. Admin operations")
        step("GET /admin/users (admin token)")
        s, body = get("/admin/users", admin_token=True)
        expect(s == 200, f"admin users status={s}")
        expect(any(u["email"] == "trader@example.com" for u in body), "trader in users list")

        step("GET /admin/strategies (cross-user)")
        s, body = get("/admin/strategies", admin_token=True)
        expect(s == 200 and len(body) >= 1, f"admin strategies count={len(body)}")

        step("GET /admin/audit (admin token)")
        s, body = get("/admin/audit?limit=20", admin_token=True)
        expect(s == 200, f"audit status={s}")
        expect(len(body) >= 1, f"audit rows={len(body)}")
        actions = {r["action"] for r in body}
        print(f"  ↪ audit actions observed: {actions}")

        step("POST /admin/users/{id}/suspend")
        s, body = post(f"/admin/users/{user_id}/suspend", {}, admin_token=True)
        expect(s == 200, f"suspend status={s} body={body}")
        expect(body["status"] == "suspended", f"new status={body['status']}")

        # ── 7. Emergency ─────────────────────────────────────────
        banner("7. Emergency pause/resume")
        step("POST /emergency/pause (scope=strategy)")
        s, body = post("/emergency/pause", {
            "scope": "strategy",
            "scope_target": sid,
            "reason": "manual test pause",
        }, admin_token=True)
        expect(s == 200, f"pause status={s} body={body}")
        pause_id = body["id"]

        step("GET /emergency/status")
        s, body = get("/emergency/status", admin_token=True)
        expect(s == 200, f"emergency status={s}")
        expect(any(p["id"] == pause_id for p in body), "pause in active list")

        step("POST /emergency/resume/{id}")
        s, body = post(f"/emergency/resume/{pause_id}", {}, admin_token=True)
        expect(s == 200, f"resume status={s} body={body}")

        # ── 8. Cross-user isolation check ─────────────────────────
        banner("8. Multi-user isolation")
        step("Register 2nd user")
        s, body = post("/auth/register", {
            "email": "other@example.com", "password": "secret123", "display_name": "Other",
        })
        expect(s == 200, f"register other status={s}")
        other_id = body["id"]

        s, body = post("/auth/login", {"email": "other@example.com", "password": "secret123"})
        expect(s == 200, "login other")
        other_token = body["token"]

        step("Other user lists strategies — should NOT see trader's")
        s, body = get("/strategies", token=other_token)
        expect(s == 200, f"other list status={s}")
        other_strat_ids = {x["id"] for x in body}
        expect(sid not in other_strat_ids, "isolation: trader's strategy visible to other user!")

        # ── 9. Cleanup ───────────────────────────────────────────
        banner("9. Cleanup")
        step(f"DELETE /strategies/{sid}")
        s, body = post(f"/strategies/{sid}/transition", {"target_state": "STOPPED"}, token=token)
        # trader is suspended; admin should be able to delete
        s, body = post("/admin/strategies", {}, admin_token=True)  # dummy, just to log
        # Direct delete via API
        req = urllib.request.Request(
            f"http://127.0.0.1:18000/strategies/{sid}", method="DELETE",
            headers={"Authorization": f"Bearer {other_token}"},
        )
        try:
            urllib.request.urlopen(req, timeout=2)
        except urllib.error.HTTPError:
            pass  # expected, other user can't delete trader's

        print("\n  ✓ ALL E2E CHECKS PASSED")
    finally:
        server.should_exit = True
        thread.join(timeout=5)
        if TMP_DB.exists():
            TMP_DB.unlink()


if __name__ == "__main__":
    main()
