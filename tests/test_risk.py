from decimal import Decimal

import pytest

from app.risk import PositionSizer, RiskManager, StopLossCalculator, TakeProfitCalculator


def test_position_size_uses_stop_distance_and_step_size():
    size = PositionSizer(Decimal("0.01")).calculate(Decimal("1000"), Decimal("100"), Decimal("98"))
    assert size == Decimal("5.000")


def test_risk_manager_rejects_daily_loss():
    manager = RiskManager(Decimal("30"), 3, Decimal("0.7"), 5)
    decision = manager.approve(Decimal("0.9"), Decimal("-30"), 0, 3)
    assert decision.approved is False


def test_risk_manager_rejects_low_confidence():
    manager = RiskManager(Decimal("30"), 3, Decimal("0.7"), 5)
    assert manager.approve(Decimal("0.69"), Decimal("0"), 0, 3).approved is False


def test_stop_and_target_follow_trade_direction():
    stop = StopLossCalculator().percentage(Decimal("100"), "BUY", Decimal("2"))
    target = TakeProfitCalculator().risk_reward(Decimal("100"), stop, "BUY")
    assert stop == Decimal("98")
    assert target == Decimal("104")


def test_sizer_rejects_invalid_stop():
    with pytest.raises(ValueError):
        PositionSizer(Decimal("0.01")).calculate(Decimal("1000"), Decimal("100"), Decimal("100"))


def test_risk_manager_blocks_exposure_and_loss_streak():
    manager = RiskManager(Decimal("30"), 3, Decimal("0.7"), 5, Decimal("100"), 2)
    manager.record_trade(Decimal("-1"))
    manager.record_trade(Decimal("-1"))
    assert manager.approve(Decimal("0.9"), Decimal("0"), 0, 3).approved is False
    assert manager.approve(Decimal("0.9"), Decimal("0"), 0, 3, Decimal("100")).approved is False


def test_emergency_stop_can_be_activated_and_reset():
    manager = RiskManager(Decimal("30"), 3, Decimal("0.7"), 5)
    manager.activate_emergency_stop("test")
    assert manager.approve(Decimal("0.9"), Decimal("0"), 0, 3).approved is False
    manager.reset_emergency_stop()
    assert manager.approve(Decimal("0.9"), Decimal("0"), 0, 3).approved is True


def test_emergency_stop_records_reason():
    manager = RiskManager(Decimal("30"), 3, Decimal("0.7"), 5)
    manager.activate_emergency_stop("manual admin")
    assert manager.emergency_stop_reason == "manual admin"
    assert "manual admin" in manager.approve(Decimal("0.9"), Decimal("0"), 0, 3).reason


def test_consecutive_losses_auto_emergency_stop():
    manager = RiskManager(Decimal("30"), 3, Decimal("0.7"), 5, max_consecutive_losses=2)
    manager.record_trade(Decimal("-1"))
    assert manager.emergency_stop is False
    manager.record_trade(Decimal("-1"))
    assert manager.emergency_stop is True
    assert "2 consecutive losses" in manager.emergency_stop_reason
    assert manager.approve(Decimal("0.9"), Decimal("0"), 0, 3).approved is False


def test_drawdown_circuit_breaker_triggers_emergency_stop():
    manager = RiskManager(Decimal("30"), 3, Decimal("0.7"), 5, max_drawdown_pct=Decimal("0.10"))
    manager.update_equity(Decimal("1000"))  # peak
    # 9% drawdown — under threshold, approved
    decision = manager.approve(Decimal("0.9"), Decimal("0"), 0, 3, current_equity=Decimal("910"))
    assert decision.approved is True
    assert manager.emergency_stop is False
    # 15% drawdown — over threshold, auto-stops
    decision = manager.approve(Decimal("0.9"), Decimal("0"), 0, 3, current_equity=Decimal("850"))
    assert decision.approved is False
    assert manager.emergency_stop is True
    assert "drawdown" in manager.emergency_stop_reason


def test_snapshot_returns_risk_state():
    manager = RiskManager(Decimal("30"), 3, Decimal("0.7"), 5, max_drawdown_pct=Decimal("0.15"))
    snap = manager.snapshot()
    assert snap["emergency_stop"] is False
    assert snap["consecutive_losses"] == 0
    assert snap["max_drawdown_pct"] == "0.15"
    assert snap["max_open_positions"] == 3
    assert snap["max_leverage"] == 5
