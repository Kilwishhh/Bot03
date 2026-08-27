"""Signal data model and engine.

Note: SignalEngine is lazily exported to avoid a circular import with
app.strategy.base (strategy imports signals.models; signals.signal_engine
imports strategy.base). Import it directly from this module at runtime,
or use ``from app.signals.signal_engine import SignalEngine``.
"""
from .models import Signal, SignalSide

__all__ = ["Signal", "SignalSide"]


def __getattr__(name: str):
    if name == "SignalEngine":
        from .signal_engine import SignalEngine

        return SignalEngine
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
