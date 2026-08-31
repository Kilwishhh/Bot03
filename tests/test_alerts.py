"""Phase 4 — OperationalAlertManager tests.

Verifies the alert manager:
- Cooldown prevents duplicate notifications
- Threshold triggers after N consecutive failures
- Recovery notification fires when failures reset
- Stale market data alert path works
- Missing notifier is a no-op (does not raise)
"""

from app.monitoring.alerts import OperationalAlertManager


class FakeNotifier:
    def __init__(self):
        self.messages: list[str] = []

    def send(self, message: str) -> None:
        self.messages.append(message)


def test_alert_manager_without_notifier_does_not_raise():
    """No notifier is a safe default — no exceptions, no NPEs."""
    manager = OperationalAlertManager(notifier=None)
    manager.record_cycle_failure(RuntimeError("boom"))
    manager.record_cycle_success()
    manager.record_stale_market_data("BTCUSDT")


def test_alert_manager_triggers_after_threshold():
    """After 3 consecutive failures, the alert fires once."""
    notifier = FakeNotifier()
    manager = OperationalAlertManager(
        notifier=notifier, failure_threshold=3, cooldown_seconds=0
    )
    for _ in range(3):
        manager.record_cycle_failure(RuntimeError("boom"))
    assert len(notifier.messages) == 1
    assert "threshold reached" in notifier.messages[0].lower()


def test_alert_manager_cooldown_prevents_spam():
    """Within the cooldown window, repeat triggers do not re-send."""
    notifier = FakeNotifier()
    manager = OperationalAlertManager(
        notifier=notifier, failure_threshold=3, cooldown_seconds=900
    )
    for _ in range(6):
        manager.record_cycle_failure(RuntimeError("boom"))
    assert len(notifier.messages) == 1, "cooldown should suppress duplicates"


def test_alert_manager_recovery_notification():
    """After recovery, a single recovery message is sent."""
    notifier = FakeNotifier()
    manager = OperationalAlertManager(
        notifier=notifier, failure_threshold=3, cooldown_seconds=0
    )
    for _ in range(3):
        manager.record_cycle_failure(RuntimeError("boom"))
    manager.record_cycle_success()
    assert len(notifier.messages) == 2
    assert "recovered" in notifier.messages[1].lower()


def test_alert_manager_recovery_resets_counter():
    """A single success resets the failure counter."""
    notifier = FakeNotifier()
    manager = OperationalAlertManager(
        notifier=notifier, failure_threshold=3, cooldown_seconds=0
    )
    for _ in range(2):
        manager.record_cycle_failure(RuntimeError("boom"))
    manager.record_cycle_success()  # resets the counter
    # Now even more failures shouldn't fire until threshold is hit again
    for _ in range(2):
        manager.record_cycle_failure(RuntimeError("boom"))
    assert len(notifier.messages) == 0, "counter should be reset by success"


def test_alert_manager_stale_market_data():
    """Stale market data alert uses its own cooldown key."""
    notifier = FakeNotifier()
    manager = OperationalAlertManager(
        notifier=notifier, failure_threshold=99, cooldown_seconds=0
    )
    manager.record_stale_market_data("BTCUSDT")
    manager.record_stale_market_data("ETHUSDT")
    assert len(notifier.messages) == 2
    assert "BTCUSDT" in notifier.messages[0]
    assert "ETHUSDT" in notifier.messages[1]


def test_alert_manager_notifier_exception_is_swallowed():
    """If the notifier raises, the manager does not propagate."""
    class BrokenNotifier:
        def send(self, message: str) -> None:
            raise ConnectionError("telegram down")

    manager = OperationalAlertManager(
        notifier=BrokenNotifier(), failure_threshold=3, cooldown_seconds=0
    )
    for _ in range(3):
        manager.record_cycle_failure(RuntimeError("boom"))
    # No exception means success
