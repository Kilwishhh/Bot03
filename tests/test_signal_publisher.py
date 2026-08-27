from datetime import UTC, datetime, timedelta

import pytest

from app.notifications import BinanceSquarePublisher, DeduplicatingPublisher, SignalPublisher, format_signal
from app.signals import Signal, SignalSide


def test_signal_format_is_safe_for_public_posting():
    signal = Signal("BTCUSDT", SignalSide.BUY, 0.8, datetime.now(UTC), ["EMA bullish"])
    assert format_signal(signal) == "BTCUSDT BUY confidence=0.80\nEMA bullish"


def test_square_publisher_is_disabled_without_supported_api():
    with pytest.raises(NotImplementedError):
        BinanceSquarePublisher().publish(Signal("BTCUSDT", SignalSide.HOLD, 0, datetime.now(UTC)))


def test_duplicate_signal_is_published_once():
    class Recorder(SignalPublisher):
        def __init__(self):
            self.messages = 0

        def publish(self, signal):
            self.messages += 1

    recorder = Recorder()
    publisher = DeduplicatingPublisher(recorder, timedelta(minutes=15))
    signal = Signal("BTCUSDT", SignalSide.BUY, 0.8, datetime.now(UTC))
    publisher.publish(signal)
    publisher.publish(signal)
    assert recorder.messages == 1
