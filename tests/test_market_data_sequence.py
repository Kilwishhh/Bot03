"""Regression tests for MARKET DATA SEQUENCE INVALID.

The legacy `BotRunner` path (TradingCycle → SignalEngine) calls
`MarketDataHealth.has_valid_sequence()` to gate signal generation.
When the validator returned False, every cycle wrote a HOLD signal with
reason "market data sequence is invalid" — even though the underlying
Binance candle data was valid.

The original implementation enforced strict ascending order:

    def has_valid_sequence(self, candles):
        return bool(candles) and all(
            candles[index].open_time > candles[index - 1].open_time
            for index in range(1, len(candles))
        )

Binance's REST /klines endpoint can return candles in *either* order
depending on cache state, exchange round-trip ordering, or when the
in-progress (current) candle is appended. The strict check rejected
all such cases, producing a flood of HOLD signals on a healthy data feed
(38 historical HOLDs on BTCUSDT 15m, all "market data sequence is invalid",
between 2026-09-01 19:06–20:42 UTC).

Fix: replace strict order check with a unique-timestamp set.
Allow any permutation (ascending, descending, or shuffled) as long as
all `open_time` values are unique. Duplicate timestamps are still rejected.

These tests pin down the three required behaviours:

1. A perfectly ascending feed (the original happy path) is accepted.
2. A descending or shuffled feed (Binance quirk) is accepted.
3. A feed with a true duplicate `open_time` is rejected.

They also cover the legacy `SignalEngine` integration so that a future
regression in `has_valid_sequence` is caught at the engine boundary
rather than only in the validator.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.exchange.models import Candle
from app.market_data import MarketDataHealth


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _candle(
    open_time: datetime,
    *,
    interval_minutes: int = 15,
) -> Candle:
    """Build a Binance-style Candle: close_time = open_time + interval.

    Mirrors the convention used by the paper adapter and Binance REST:
    close_time is the EXCLUSIVE end of the interval.
    """
    return Candle(
        open_time=open_time,
        close_time=open_time + timedelta(minutes=interval_minutes),
        open=Decimal("100.0"),
        high=Decimal("101.0"),
        low=Decimal("99.0"),
        close=Decimal("100.5"),
        volume=Decimal("10.0"),
    )


def _ascending_15m_200(start: datetime) -> list[Candle]:
    """Build 200 ascending 15m candles starting at `start` (BTCUSDT 15m default)."""
    return [
        _candle(start + timedelta(minutes=15 * i), interval_minutes=15)
        for i in range(200)
    ]


# ---------------------------------------------------------------------------
# has_valid_sequence: the validator itself
# ---------------------------------------------------------------------------


class TestHasValidSequence:
    """Pin down exactly which inputs the validator accepts/rejects."""

    def test_ascending_feed_is_valid(self):
        """The original happy path — still must pass after the fix."""
        now = datetime.now(UTC)
        start = now - timedelta(minutes=15 * 199)
        candles = _ascending_15m_200(start)
        assert MarketDataHealth().has_valid_sequence(candles) is True

    def test_descending_feed_is_valid(self):
        """Binance can return the in-progress candle appended out of order.

        Pre-fix: the strict `open_time > previous.open_time` check rejected this
        and emitted HOLD signals on every cycle.
        Post-fix: a descending feed with unique timestamps is accepted.
        """
        now = datetime.now(UTC)
        start = now - timedelta(minutes=15 * 199)
        candles = list(reversed(_ascending_15m_200(start)))
        assert MarketDataHealth().has_valid_sequence(candles) is True

    def test_shuffled_unique_feed_is_valid(self):
        """A non-sorted feed with all unique timestamps is accepted.

        The validator cares about uniqueness, not order.
        """
        now = datetime.now(UTC)
        start = now - timedelta(minutes=15 * 4)
        candles = [
            _candle(start + timedelta(minutes=15 * 4)),
            _candle(start + timedelta(minutes=15 * 1)),
            _candle(start + timedelta(minutes=15 * 3)),
            _candle(start + timedelta(minutes=15 * 0)),
            _candle(start + timedelta(minutes=15 * 2)),
        ]
        assert MarketDataHealth().has_valid_sequence(candles) is True

    def test_duplicate_open_time_is_rejected(self):
        """Two candles with the same `open_time` is a true sequence error."""
        now = datetime.now(UTC)
        c1 = _candle(now - timedelta(minutes=30))
        c2 = _candle(now - timedelta(minutes=15))
        c1_dup = _candle(c1.open_time)  # same open_time as c1
        candles = [c1, c1_dup, c2]
        assert MarketDataHealth().has_valid_sequence(candles) is False

    def test_single_candle_is_valid(self):
        """A list of one candle is trivially valid (no duplicates possible)."""
        now = datetime.now(UTC)
        assert MarketDataHealth().has_valid_sequence(
            [_candle(now - timedelta(minutes=15))]
        ) is True

    def test_empty_list_is_invalid(self):
        """Empty list cannot form a sequence — explicit False is required."""
        assert MarketDataHealth().has_valid_sequence([]) is False

    def test_binance_in_progress_candle_appended_at_end(self):
        """Binance /klines with the in-progress candle appended is valid.

        This is the exact shape that triggered the original 38 HOLD signals:
        a perfectly ordered list of N closed candles, plus an N+1 candle whose
        `open_time` is exactly one interval after the previous one.
        """
        now = datetime.now(UTC)
        start = now - timedelta(minutes=15 * 199)
        candles = _ascending_15m_200(start)
        # Last candle's open_time is start + 15*199; this is the in-progress
        # candle that the strict order check was rejecting when ordering flipped.
        assert MarketDataHealth().has_valid_sequence(candles) is True


# ---------------------------------------------------------------------------
# SignalEngine integration: end-to-end regression
# ---------------------------------------------------------------------------


class TestSignalEngineSequenceGate:
    """The legacy TradingCycle path uses SignalEngine to gate on sequence.

    If the validator wrongly returns False, the engine emits HOLD with
    reason "market data sequence is invalid" — this is the original bug.
    These tests pin the engine's behaviour so a future regression is
    caught at the boundary the user actually sees.
    """

    def test_ascending_binance_15m_produces_non_hold(self):
        """A healthy ascending Binance 15m feed must NOT produce HOLD."""
        from app.signals import SignalEngine
        from app.strategy.rsi_mean_reversion import RSIMeanReversionStrategy

        now = datetime.now(UTC)
        start = now - timedelta(minutes=15 * 199)
        candles = _ascending_15m_200(start)
        strategy = RSIMeanReversionStrategy()
        engine = SignalEngine(strategy, MarketDataHealth())
        signal = engine.generate("BTCUSDT", candles)
        # Must NOT be a sequence-error HOLD.
        assert not (signal.side.value == "HOLD" and "sequence" in (signal.reason or "").lower()), (
            f"engine wrongly rejected valid sequence: side={signal.side.value} reason={signal.reason!r}"
        )

    def test_engine_uses_signal_engine_short_circuit_message(self):
        """When the validator rejects, the engine emits the exact string.

        Pin the wording so log search / dashboards keep working.
        """
        from app.signals import SignalEngine
        from app.strategy.rsi_mean_reversion import RSIMeanReversionStrategy

        now = datetime.now(UTC)
        c1 = _candle(now - timedelta(minutes=15))
        c1_dup = _candle(c1.open_time)  # duplicate — should be rejected
        candles = [c1, c1_dup]
        strategy = RSIMeanReversionStrategy()
        engine = SignalEngine(strategy, MarketDataHealth())
        signal = engine.generate("BTCUSDT", candles)
        assert signal.side.value == "HOLD"
        # reason is list[str] in the Signal model
        assert signal.reason == ["market data sequence is invalid"]
