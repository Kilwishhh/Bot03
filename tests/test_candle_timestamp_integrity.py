"""P0-02..P0-03: Candle timestamp integrity — regression tests.

Tests closed-candle selection, age validation, and timestamp semantics.
"""

import pytest
from datetime import datetime, timedelta, UTC
from decimal import Decimal
from app.exchange.models import Candle
from app.strategy.scanner import (
    _candle_age_seconds,
    _is_candle_closed,
    _select_last_closed_candle,
)


def c(open_minute: int, interval: str = "1m") -> Candle:
    """Build a Candle whose close_time is the EXCLUSIVE end of the interval.

    For 1m candle starting at minute `open_minute`:
      open_time  = open_minute:00
      close_time = open_minute+1:00  (exclusive — next candle's start)

    This matches Binance kline semantics.
    """
    base = datetime(2026, 9, 2, 18, open_minute, 0, tzinfo=UTC)
    delta = timedelta(minutes={"1m": 1, "5m": 5, "15m": 15}.get(interval, 1))
    return Candle(
        open_time=base,
        close_time=base + delta,
        open=Decimal("100.0"),
        high=Decimal("101.0"),
        low=Decimal("99.0"),
        close=Decimal("100.5"),
        volume=Decimal("10.0"),
    )


class TestBinanceCloseTimeSemantics:
    """Verify that close_time is EXCLUSIVE (next candle's start)."""

    def test_1m_candle_close_time_is_next_minute_start(self):
        candle = c(open_minute=36)  # 18:36:00 → close=18:37:00
        assert candle.close_time == datetime(2026, 9, 2, 18, 37, 0, tzinfo=UTC)
        assert candle.close_time > candle.open_time

    def test_5m_candle_close_time_is_5_minutes_later(self):
        candle = c(open_minute=30, interval="5m")
        assert candle.close_time == datetime(2026, 9, 2, 18, 35, 0, tzinfo=UTC)


class TestIsCandleClosed:
    def test_in_progress_candle_is_not_closed(self):
        now = datetime(2026, 9, 2, 18, 36, 50, tzinfo=UTC)  # 18:36:50
        candle = c(open_minute=36)  # close_time=18:37:00
        assert not _is_candle_closed(candle, now)

    def test_just_closed_candle_is_closed(self):
        now = datetime(2026, 9, 2, 18, 37, 0, 0, tzinfo=UTC)  # exactly at close_time
        candle = c(open_minute=36)  # close_time=18:37:00
        assert _is_candle_closed(candle, now)

    def test_completed_candle_is_closed(self):
        now = datetime(2026, 9, 2, 18, 37, 30, tzinfo=UTC)  # 30s after close
        candle = c(open_minute=36)  # close_time=18:37:00
        assert _is_candle_closed(candle, now)


class TestSelectLastClosedCandle:
    def test_empty_list_returns_none(self):
        assert _select_last_closed_candle([]) is None

    def test_all_in_progress_returns_none(self):
        now = datetime(2026, 9, 2, 18, 36, 50, tzinfo=UTC)
        candles = [c(open_minute=36), c(open_minute=37)]  # close=18:37, 18:38
        result = _select_last_closed_candle(candles, now)
        # reversed: [c(37), c(36)]. c(37): 18:38 > 18:36:50 → skip. c(36): 18:37 > 18:36:50 → skip. return None.
        assert result is None

    def test_last_candle_is_closed_returns_it(self):
        now = datetime(2026, 9, 2, 18, 38, 10, tzinfo=UTC)
        candles = [c(open_minute=36), c(open_minute=37)]
        result = _select_last_closed_candle(candles, now)
        assert result is not None
        assert result.open_time == datetime(2026, 9, 2, 18, 37, 0, tzinfo=UTC)

    def test_earlier_candle_closed_later_not(self):
        now = datetime(2026, 9, 2, 18, 37, 0, 0, tzinfo=UTC)  # exactly at close of minute 36
        candles = [c(open_minute=36), c(open_minute=37)]
        result = _select_last_closed_candle(candles, now)
        # 36 is closed (18:37:00 >= 18:37:00), 37 is not (18:38:00 > 18:37:00)
        assert result is not None
        assert result.open_time == datetime(2026, 9, 2, 18, 36, 0, tzinfo=UTC)

    def test_entire_list_in_progress_returns_none(self):
        now = datetime(2026, 9, 2, 18, 34, 30, tzinfo=UTC)  # before either candle is closed
        candles = [c(open_minute=34), c(open_minute=35)]  # close=18:35, 18:36
        result = _select_last_closed_candle(candles, now)
        # reversed: [c(35), c(34)]. c(35): 18:36 > 18:34:30? Yes → skip. c(34): 18:35 > 18:34:30? Yes → skip. return None.
        assert result is None

    def test_naive_timestamp_converted_to_utc(self):
        """TZ-aware and naive timestamps both handled."""
        candle_naive = Candle(
            open_time=datetime(2026, 9, 2, 18, 36, 0),
            close_time=datetime(2026, 9, 2, 18, 37, 0),
            open=Decimal("100"), high=Decimal("101"),
            low=Decimal("99"), close=Decimal("100.5"),
            volume=Decimal("10"),
        )
        now = datetime(2026, 9, 2, 18, 37, 30, tzinfo=UTC)
        result = _select_last_closed_candle([candle_naive], now)
        assert result is not None

    def test_future_candle_skipped(self):
        """A candle with close_time in the future (clock skew) is skipped."""
        future_candle = Candle(
            open_time=datetime(2026, 9, 2, 18, 38, 0, tzinfo=UTC),
            close_time=datetime(2026, 9, 2, 18, 39, 0, tzinfo=UTC),
            open=Decimal("100"), high=Decimal("101"),
            low=Decimal("99"), close=Decimal("100.5"),
            volume=Decimal("10"),
        )
        closed_candle = c(open_minute=36)
        now = datetime(2026, 9, 2, 18, 37, 30, tzinfo=UTC)
        result = _select_last_closed_candle([closed_candle, future_candle], now)
        assert result is not None
        assert result.open_time == datetime(2026, 9, 2, 18, 36, 0, tzinfo=UTC)


class TestCandleAgeSeconds:
    def test_completed_candle_age_is_positive(self):
        now = datetime(2026, 9, 2, 18, 37, 30, tzinfo=UTC)
        candle = c(open_minute=36)  # close_time=18:37:00
        age = _candle_age_seconds(candle, now)
        assert age == 30.0  # 18:37:30 - 18:37:00 = 30s

    def test_in_progress_candle_age_is_negative(self):
        now = datetime(2026, 9, 2, 18, 36, 52, tzinfo=UTC)
        candle = c(open_minute=36)  # close_time=18:37:00
        age = _candle_age_seconds(candle, now)
        assert age == -8.0  # 18:36:52 - 18:37:00 = -8s

    def test_just_closed_candle_age_is_zero(self):
        now = datetime(2026, 9, 2, 18, 37, 0, 0, tzinfo=UTC)
        candle = c(open_minute=36)
        age = _candle_age_seconds(candle, now)
        assert age == 0.0

    def test_age_with_naive_timestamp_uses_utc(self):
        """Naive timestamps are treated as UTC for age calculation."""
        candle = Candle(
            open_time=datetime(2026, 9, 2, 18, 36, 0),
            close_time=datetime(2026, 9, 2, 18, 37, 0),
            open=Decimal("100"), high=Decimal("101"),
            low=Decimal("99"), close=Decimal("100.5"),
            volume=Decimal("10"),
        )
        age = _candle_age_seconds(candle)
        # Should not raise — naive handled
        assert isinstance(age, float)
