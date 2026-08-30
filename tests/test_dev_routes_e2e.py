"""E2E tests for /dev paper-trading endpoints.

Tests the complete paper-trade pipeline:
  Strategy → Signal → Paper Order → Filled Order → Position → TP/SL → Closed Trade → PnL
"""
from decimal import Decimal
from fastapi.testclient import TestClient


def test_simulate_signal_generates_signals_and_opens_positions(client: TestClient):
    """POST /dev/strategies/{id}/simulate-signal produces signals + open positions."""
    STRAT = "47ddb081-d9bb-454d-bc67-f715d96ef6c4"

    # Clean slate
    r = client.delete(f"/dev/strategies/{STRAT}/reset")
    assert r.status_code == 200

    # Generate signals
    r = client.post(f"/dev/strategies/{STRAT}/simulate-signal")
    assert r.status_code == 200
    body = r.json()
    assert body["strategy_id"] == STRAT

    generated = [x for x in body["results"] if x["outcome"] == "signal_generated"]
    assert len(generated) == 3, f"Expected 3 signals, got: {body['results']}"

    for sig in generated:
        assert sig["entry"] is not None
        assert sig["tp"] is not None
        assert sig["sl"] is not None
        if sig["direction"] == "BUY":
            assert sig["sl"] < sig["entry"] < sig["tp"], (
                f"BUY: SL < entry < TP, got sl={sig['sl']} entry={sig['entry']} tp={sig['tp']}"
            )
        else:  # SELL
            assert sig["tp"] < sig["entry"] < sig["sl"], (
                f"SELL: TP < entry < SL, got tp={sig['tp']} entry={sig['entry']} sl={sig['sl']}"
            )


def test_drive_close_tp_closes_at_tp_price(client: TestClient):
    """POST /dev/strategies/{id}/drive-close target=tp hits take-profit and produces profit."""
    STRAT = "47ddb081-d9bb-454d-bc67-f715d96ef6c4"
    client.delete(f"/dev/strategies/{STRAT}/reset")
    body = client.post(f"/dev/strategies/{STRAT}/simulate-signal").json()

    for sig in body["results"]:
        if sig["outcome"] != "signal_generated":
            continue
        sym = sig["symbol"]
        tp_before = sig["tp"]
        balance_before = client.post(
            f"/dev/strategies/{STRAT}/drive-close",
            json={"symbol": sym, "target": "tp"},
        ).json()
        assert balance_before["closed"] is True, f"{sym} should be closed at TP"
        # drove_price_to must be the TP price, not the SL price
        assert balance_before["drove_price_to"] == tp_before, f"{sym} drove to {balance_before['drove_price_to']} but TP={tp_before}"


def test_drive_close_sl_closes_at_sl_price(client: TestClient):
    """POST /dev/strategies/{id}/drive-close target=sl hits stop-loss and produces loss."""
    STRAT = "47ddb081-d9bb-454d-bc67-f715d96ef6c4"
    client.delete(f"/dev/strategies/{STRAT}/reset")
    body = client.post(f"/dev/strategies/{STRAT}/simulate-signal").json()

    for sig in body["results"]:
        if sig["outcome"] != "signal_generated":
            continue
        sym = sig["symbol"]
        sl_before = sig["sl"]
        result = client.post(
            f"/dev/strategies/{STRAT}/drive-close",
            json={"symbol": sym, "target": "sl"},
        ).json()
        assert result["closed"] is True, f"{sym} should be closed at SL"
        assert result["drove_price_to"] == sl_before, f"{sym} drove to {result['drove_price_to']} but SL={sl_before}"


def test_result_endpoint_shows_trades_and_pnl(client: TestClient):
    """GET /dev/strategies/{id}/result includes trades with exit_price and realized_pnl."""
    STRAT = "47ddb081-d9bb-454d-bc67-f715d96ef6c4"
    client.delete(f"/dev/strategies/{STRAT}/reset")
    sigs = client.post(f"/dev/strategies/{STRAT}/simulate-signal").json()["results"]

    for sig in sigs:
        if sig["outcome"] != "signal_generated":
            continue
        client.post(
            f"/dev/strategies/{STRAT}/drive-close",
            json={"symbol": sig["symbol"], "target": "tp"},
        )

    result = client.get(f"/dev/strategies/{STRAT}/result").json()
    assert result["summary"]["signals_count"] == 3
    assert result["summary"]["closed_trades"] >= 3
    assert result["summary"]["total_realized_pnl"] > 0, "TP closes should produce positive PnL"
    assert len(result["open_positions"]) == 0, "All positions should be closed"

    for t in result["trades"]:
        if t.get("exit_price") is not None:
            assert t.get("realized_pnl") is not None


def test_reset_clears_all_state(client: TestClient):
    """DELETE /dev/strategies/{id}/reset wipes signals, trades, and positions."""
    STRAT = "47ddb081-d9bb-454d-bc67-f715d96ef6c4"

    # Create some state
    client.post(f"/dev/strategies/{STRAT}/simulate-signal")
    r = client.delete(f"/dev/strategies/{STRAT}/reset")
    assert r.status_code == 200

    result = client.get(f"/dev/strategies/{STRAT}/result").json()
    assert result["summary"]["signals_count"] == 0
    assert result["summary"]["trades_count"] == 0
    assert len(result["open_positions"]) == 0
