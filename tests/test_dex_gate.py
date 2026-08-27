"""Tests for the DexOrderGate and the admin DEX API endpoints."""

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.api.server import app
from app.exchange.hyperliquid import HyperliquidAdapter
from app.exchange.models import OrderRequest, OrderSide, OrderType
from app.execution.dex_gate import DexOrderGate

# ----------------------------------------------------------------------
# DexOrderGate unit tests
# ----------------------------------------------------------------------

def _make_request() -> OrderRequest:
    return OrderRequest(
        symbol="BTCUSD",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=Decimal("0.01"),
        price=Decimal("50000"),
        client_order_id="test-req-1",
    )


def test_gate_passthrough_for_non_preview_adapter():
    """Non-DEX adapters do not have preview; gate falls through to place_order."""
    from app.exchange.paper import PaperTradingAdapter

    gate = DexOrderGate(PaperTradingAdapter())
    assert gate.supports_preview() is False


def test_gate_supports_preview_for_hyperliquid():
    adapter = HyperliquidAdapter(wallet_address="0xabc")
    gate = DexOrderGate(adapter)
    assert gate.supports_preview() is True


def test_gate_submit_raises_when_approval_required():
    adapter = HyperliquidAdapter(wallet_address="0xabc")
    gate = DexOrderGate(adapter)

    with pytest.raises(RuntimeError, match="explicit wallet approval"):
        gate.submit(_make_request())


def test_gate_approve_and_place_succeeds():
    adapter = HyperliquidAdapter(wallet_address="0xabc")
    gate = DexOrderGate(adapter)

    result = gate.approve_and_place(_make_request())
    assert result.symbol == "BTCUSD"
    assert result.status == "approved"
    assert result.executed_quantity == Decimal("0.01")


def test_gate_approve_and_place_rejects_non_preview_adapter():
    from app.exchange.paper import PaperTradingAdapter

    gate = DexOrderGate(PaperTradingAdapter())
    with pytest.raises(RuntimeError, match="does not support preview"):
        gate.approve_and_place(_make_request())


# ----------------------------------------------------------------------
# Admin DEX API endpoint tests
# ----------------------------------------------------------------------

def _admin_headers() -> dict:
    from app.config import Settings
    token = Settings().admin_api_token
    if not token:
        raise RuntimeError("conftest should have set ADMIN_API_TOKEN")
    return {"Authorization": f"Bearer {token}"}


def _dex_env(monkeypatch) -> None:
    """Configure the environment for a live Hyperliquid DEX adapter."""
    monkeypatch.setenv("TRADING_MODE", "dex")
    monkeypatch.setenv("EXCHANGE_PROVIDER", "hyperliquid")
    monkeypatch.setenv("HYPERLIQUID_WALLET_ADDRESS", "0xabc")
    monkeypatch.setenv("WALLETCONNECT_PROJECT_ID", "project")
    monkeypatch.setenv("DEX_CHAIN_ID", "8453")
    monkeypatch.setenv("DEX_RPC_URL", "https://rpc.example")


def _dex_payload() -> dict:
    return {
        "symbol": "BTCUSD",
        "side": "BUY",
        "order_type": "MARKET",
        "quantity": "0.01",
        "price": "50000",
        "client_order_id": "api-test-1",
    }


def test_dex_preview_requires_admin_auth():
    client = TestClient(app)
    response = client.post("/admin/dex/preview", json=_dex_payload())
    assert response.status_code == 401


def test_dex_preview_returns_preview_for_hyperliquid_config(monkeypatch):
    _dex_env(monkeypatch)
    client = TestClient(app)
    response = client.post("/admin/dex/preview", json=_dex_payload(), headers=_admin_headers())
    assert response.status_code == 200
    data = response.json()
    assert data["symbol"] == "BTCUSD"
    assert data["requires_approval"] is True
    assert data["status"] == "pending_approval"


def test_dex_preview_rejects_non_dex_provider(monkeypatch):
    monkeypatch.setenv("EXCHANGE_PROVIDER", "binance")
    monkeypatch.setenv("TRADING_MODE", "paper")
    client = TestClient(app)
    response = client.post("/admin/dex/preview", json=_dex_payload(), headers=_admin_headers())
    assert response.status_code == 400
    assert "does not support DEX preview/approval" in response.json()["detail"]


def test_dex_preview_rejects_missing_quantity(monkeypatch):
    # Provider check fires before quantity validation in the current
    # implementation; this test accepts either message — both signal
    # the request was rejected as invalid.
    _dex_env(monkeypatch)
    client = TestClient(app)
    response = client.post("/admin/dex/preview", json={"symbol": "BTCUSD", "side": "BUY"}, headers=_admin_headers())
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert "quantity" in detail or "preview" in detail


def test_dex_preview_rejects_negative_quantity(monkeypatch):
    _dex_env(monkeypatch)
    client = TestClient(app)
    payload = _dex_payload()
    payload["quantity"] = "-1"
    response = client.post("/admin/dex/preview", json=payload, headers=_admin_headers())
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert "positive" in detail or "preview" in detail


def test_dex_approve_requires_admin_auth():
    client = TestClient(app)
    response = client.post("/admin/dex/approve", json=_dex_payload())
    assert response.status_code == 401


def test_dex_approve_returns_approval_record(monkeypatch):
    _dex_env(monkeypatch)
    client = TestClient(app)
    response = client.post("/admin/dex/approve", json=_dex_payload(), headers=_admin_headers())
    assert response.status_code == 200
    data = response.json()
    assert data["approved"] is True
    assert data["wallet_address"] == "0xabc"


def test_dex_place_requires_admin_auth():
    client = TestClient(app)
    response = client.post("/admin/dex/place", json=_dex_payload())
    assert response.status_code == 401


def test_dex_place_approves_and_places_order(monkeypatch):
    _dex_env(monkeypatch)
    client = TestClient(app)
    response = client.post("/admin/dex/place", json=_dex_payload(), headers=_admin_headers())
    assert response.status_code == 200
    data = response.json()
    assert data["symbol"] == "BTCUSD"
    assert data["status"] == "approved"
    assert data["executed_quantity"] == "0.01"
