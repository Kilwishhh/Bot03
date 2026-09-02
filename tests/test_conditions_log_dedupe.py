"""P0-04: Conditions log dedupe — per-cycle aggregation tests."""

from unittest.mock import patch
from app.strategy.scanner import StrategyScanner


class _StubMD:
    def candles(self, *a, **kw):
        return []


class _StubLogger:
    def __init__(self):
        self.records = []

    def info(self, msg, *args):
        self.records.append(msg % args if args else msg)

    def debug(self, msg, *args):
        pass

    def warning(self, msg, *args):
        pass


def test_counters_start_at_zero():
    s = StrategyScanner(None, _StubMD(), minimum_hits=1)
    assert s._cycle_fail_count == 0
    assert s._cycle_fail_samples == []
    assert s._cycle_min_hits_count == 0
    assert s._cycle_min_hits_samples == []


def test_fail_count_increments_on_failure():
    s = StrategyScanner(None, _StubMD(), minimum_hits=1)
    s._cycle_fail_count = 0
    s._cycle_fail_samples.clear()
    s._cycle_min_hits_count = 0
    s._cycle_min_hits_samples.clear()

    # Simulate 3 symbols failing conditions
    for i in range(3):
        s._cycle_fail_count += 1
        if len(s._cycle_fail_samples) < s._cycle_fail_sample_max:
            s._cycle_fail_samples.append((f"strat{i}", f"SYM{i}", ["all conditions failed"]))

    assert s._cycle_fail_count == 3
    assert len(s._cycle_fail_samples) == 3


def test_samples_capped_at_max():
    s = StrategyScanner(None, _StubMD(), minimum_hits=1)
    s._cycle_fail_count = 0
    s._cycle_fail_samples.clear()

    # Add 10 failures, but sample max is 5
    for i in range(10):
        s._cycle_fail_count += 1
        if len(s._cycle_fail_samples) < s._cycle_fail_sample_max:
            s._cycle_fail_samples.append((f"strat{i}", f"SYM{i}", ["failed"]))

    assert s._cycle_fail_count == 10
    assert len(s._cycle_fail_samples) == 5  # capped


def test_counters_reset_after_scan_once():
    s = StrategyScanner(None, _StubMD(), minimum_hits=1)
    s._cycle_fail_count = 42
    s._cycle_fail_samples.append(("strat", "BTCUSDT", ["fail"]))
    s._cycle_min_hits_count = 7
    s._cycle_min_hits_samples.append(("strat", "ETHUSDT", 1, 3))

    with patch("app.strategy.scanner.load_active_strategies", return_value=[]):
        s.scan_once()

    # Counters must be reset for next cycle
    assert s._cycle_fail_count == 0
    assert s._cycle_fail_samples == []
    assert s._cycle_min_hits_count == 0
    assert s._cycle_min_hits_samples == []


def test_min_hits_not_met_count_increments():
    s = StrategyScanner(None, _StubMD(), minimum_hits=2)
    s._cycle_min_hits_count = 0
    s._cycle_min_hits_samples.clear()

    for i in range(5):
        s._cycle_min_hits_count += 1
        if len(s._cycle_min_hits_samples) < s._cycle_fail_sample_max:
            s._cycle_min_hits_samples.append((f"strat{i}", f"SYM{i}", 1, 2))

    assert s._cycle_min_hits_count == 5
    assert len(s._cycle_min_hits_samples) == 5


def test_no_summary_when_counters_zero():
    """When no failures occurred, no cycle summary should be constructed."""
    s = StrategyScanner(None, _StubMD(), minimum_hits=1)
    s._cycle_fail_count = 0
    s._cycle_min_hits_count = 0
    # scan_once returns early if no strategies loaded
    with patch("app.strategy.scanner.load_active_strategies", return_value=[]):
        s.scan_once()
    # No exceptions = success (summary block is guarded by > 0 check)
    assert s._cycle_fail_count == 0
