"""Tests for the auto-loading of user-defined strategies."""

import sys
from pathlib import Path

from app.strategy import create_strategy
from app.strategy import factory as strategy_factory
from app.strategy.base import Strategy

USER_DIR = Path(__file__).resolve().parents[1] / "app" / "strategy" / "user_strategies"


def _make_module(name: str, contents: str):
    """Write a Python module to the user_strategies directory and import it."""
    target = USER_DIR / f"{name}.py"
    target.write_text(contents, encoding="utf-8")
    # Clear any previous import
    sys.modules.pop(f"app.strategy.user_strategies.{name}", None)
    return target


def _remove_module(name: str) -> None:
    target = USER_DIR / f"{name}.py"
    if target.exists():
        target.unlink()
    sys.modules.pop(f"app.strategy.user_strategies.{name}", None)
    # Re-run the loader so the registry reflects the current filesystem
    strategy_factory._load_user_strategies()


def test_user_strategy_via_build_function():
    name = "_test_build_fn_strategy"
    code = f"""
from app.strategy.base import Strategy

name = "{name}"


class _MyStrategy(Strategy):
    def generate_signal(self, symbol, candles):
        from app.signals.models import Signal, SignalSide
        from datetime import datetime, timezone
        return Signal(symbol, SignalSide.HOLD, 0.0, datetime.now(timezone.utc), ["test"], "test")


def build(_settings):
    return _MyStrategy()
"""
    _make_module(name, code)
    try:
        strategy_factory._load_user_strategies()
        assert strategy_factory.is_registered(name)
        from app.config import Settings
        s = create_strategy(Settings(strategy=name))
        assert isinstance(s, Strategy)
    finally:
        _remove_module(name)


def test_user_strategy_via_name_attribute():
    name = "_test_class_strategy"
    code = f"""
from app.strategy.base import Strategy

class _MyStrategy(Strategy):
    name = "{name}"

    def generate_signal(self, symbol, candles):
        from app.signals.models import Signal, SignalSide
        from datetime import datetime, timezone
        return Signal(symbol, SignalSide.HOLD, 0.0, datetime.now(timezone.utc), ["test"], "test")
"""
    _make_module(name, code)
    try:
        strategy_factory._load_user_strategies()
        assert strategy_factory.is_registered(name)
        from app.config import Settings
        s = create_strategy(Settings(strategy=name))
        assert isinstance(s, Strategy)
    finally:
        _remove_module(name)


def test_user_strategy_with_import_error_does_not_crash_app():
    name = "_test_broken_strategy"
    code = "import this_module_does_not_exist_for_sure\n"
    _make_module(name, code)
    try:
        # The loader catches the import error and logs it; the app stays alive.
        strategy_factory._load_user_strategies()
        # The broken module is not registered.
        assert not strategy_factory.is_registered(name)
    finally:
        _remove_module(name)


def test_builtin_example_strategy_is_loaded():
    """The shipped _my_first_strategy.py example should be auto-registered."""
    assert strategy_factory.is_registered("my_first_strategy")
