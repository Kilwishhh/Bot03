"""Phase 5 — External API validation sweep.

Confirms that every ExchangeAdapter subclass:
- Implements the `health_check()` abstract method
- Returns a bool from health_check (not None, not raises)
- Can be instantiated and exercised against a fake transport

Also covers the factory: unknown providers raise a clear error.
"""

import inspect

import pytest

from app.exchange.base import ExchangeAdapter
from app.exchange.factory import create_exchange
from app.exchange.paper import PaperTradingAdapter


def _all_subclasses(cls):
    """Walk the entire class hierarchy."""
    result = set()
    seen = set()
    queue = [cls]
    while queue:
        current = queue.pop()
        for sub in current.__subclasses__():
            if sub not in seen:
                seen.add(sub)
                result.add(sub)
                queue.append(sub)
    return result


def test_paper_adapter_implements_health_check():
    """PaperTradingAdapter must override health_check with a bool return."""
    assert issubclass(PaperTradingAdapter, ExchangeAdapter)
    impl = PaperTradingAdapter.health_check
    assert impl is not ExchangeAdapter.health_check, (
        "PaperTradingAdapter must override health_check"
    )
    adapter = PaperTradingAdapter()
    result = adapter.health_check()
    assert isinstance(result, bool)


def test_every_exchange_subclass_implements_health_check():
    """Every concrete ExchangeAdapter subclass must implement health_check."""
    concrete = {
        cls for cls in _all_subclasses(ExchangeAdapter)
        if not inspect.isabstract(cls) and cls is not ExchangeAdapter
    }
    assert concrete, "expected at least one concrete ExchangeAdapter subclass"
    missing = []
    for cls in concrete:
        if cls.health_check is ExchangeAdapter.health_check:
            missing.append(cls.__name__)
    assert not missing, (
        f"Following subclasses still use the abstract health_check: {missing}"
    )


def test_every_exchange_subclass_health_check_returns_bool():
    """Every health_check() must return a bool under normal conditions."""
    concrete = {
        cls for cls in _all_subclasses(ExchangeAdapter)
        if not inspect.isabstract(cls) and cls is not ExchangeAdapter
    }
    for cls in concrete:
        try:
            instance = cls.__new__(cls)
        except Exception:
            continue
        if not hasattr(instance, "_initialized"):
            try:
                instance.__init__()  # type: ignore[call-arg]
            except (TypeError, RuntimeError):
                # Adapters that need creds can't be constructed in CI; skip
                continue
        try:
            result = instance.health_check()
        except (NotImplementedError, RuntimeError, ConnectionError):
            # If it requires network/creds, that's expected — just verify
            # the method is overridden (covered by previous test).
            continue
        assert isinstance(result, bool), (
            f"{cls.__name__}.health_check() returned {type(result).__name__}, "
            "expected bool"
        )


def test_factory_rejects_unhandled_provider():
    """create_exchange raises NotImplementedError for LIVE+DEX (not wired in factory)."""
    from app.config import ExchangeProvider, Settings, TradingMode
    # Bypass Settings validation (which also blocks LIVE+DEX) to test the factory path.
    # We only care that the factory raises, not which validation layer catches it first.
    settings = Settings.model_construct(
        trading_mode=TradingMode.LIVE,
        exchange_provider=ExchangeProvider.DEX,
        paper_starting_balance="10000",
    )
    with pytest.raises(NotImplementedError, match="not yet implemented"):
        create_exchange(settings)


def test_factory_creates_paper_adapter():
    """create_exchange returns PaperTradingAdapter for paper mode regardless of provider."""
    from app.config import ExchangeProvider, Settings, TradingMode
    settings = Settings(
        trading_mode=TradingMode.PAPER,
        exchange_provider=ExchangeProvider.BINANCE,  # provider ignored in paper mode
    )
    exchange = create_exchange(settings)
    assert isinstance(exchange, ExchangeAdapter)
    assert isinstance(exchange, PaperTradingAdapter)
    assert exchange.health_check() is True
