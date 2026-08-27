"""Strategy registry + factory.

Built-in strategies are registered explicitly in this file. Custom
user-defined strategies can be dropped into ``app/strategy/user_strategies/``
and will be auto-registered on import if they expose a class with a
``name`` class attribute and accept settings in the standard shape.

A strategy is registered by:
  * Defining a subclass of :class:`app.strategy.base.Strategy`
  * Setting a unique ``name`` class attribute
  * Calling :func:`register` with a builder that accepts
    a :class:`app.config.Settings` instance and returns an instance

The factory (:func:`create_strategy`) looks up the configured
``STRATEGY`` setting and dispatches to the registered builder.
"""

from __future__ import annotations

import importlib
import importlib.util
import logging
import pkgutil
import sys
from collections.abc import Callable
from pathlib import Path

from app.config import Settings

from .base import Strategy
from .bollinger import BollingerStrategy
from .ema_crossover import EMACrossoverStrategy
from .indicator_strategy import IndicatorStrategy
from .macd_crossover import MACDCrossoverStrategy
from .rsi_mean_reversion import RSIMeanReversionStrategy

logger = logging.getLogger(__name__)


# A builder is a callable that takes Settings and returns a Strategy.
Builder = Callable[[Settings], Strategy]


_REGISTRY: dict[str, Builder] = {}


def register(name: str, builder: Builder) -> None:
    """Register a strategy under a unique name.

    Re-registering the same name overwrites the previous entry and logs a
    warning. This is intentional: a user strategy with the same name as
    a built-in should win.
    """
    if name in _REGISTRY:
        logger.warning("overriding registered strategy %r", name)
    _REGISTRY[name] = builder


def available_strategies() -> list[str]:
    """Return all registered strategy names in registration order."""
    return list(_REGISTRY.keys())


def is_registered(name: str) -> bool:
    return name in _REGISTRY


# ---- Built-in registrations --------------------------------------------

def _build_indicator(settings: Settings) -> Strategy:
    return IndicatorStrategy(
        ema_fast=settings.ema_fast,
        ema_slow=settings.ema_slow,
        rsi_period=settings.rsi_period,
        bb_period=settings.bb_period,
        adx_period=settings.adx_period,
    )


def _build_ema_crossover(settings: Settings) -> Strategy:
    return EMACrossoverStrategy(
        ema_fast=getattr(settings, "ema_fast", 9),
        ema_slow=getattr(settings, "ema_slow", 21),
    )


def _build_macd_crossover(settings: Settings) -> Strategy:
    return MACDCrossoverStrategy(
        fast=getattr(settings, "macd_fast", 12),
        slow=getattr(settings, "macd_slow", 26),
        signal_period=getattr(settings, "macd_signal", 9),
    )


def _build_bollinger(settings: Settings) -> Strategy:
    from decimal import Decimal
    return BollingerStrategy(
        period=getattr(settings, "bb_period", 20),
        std_multiplier=Decimal(str(getattr(settings, "bollinger_std", "2"))),
        mode=getattr(settings, "bollinger_mode", "breakout"),
    )


def _build_rsi_reversion(settings: Settings) -> Strategy:
    from decimal import Decimal
    return RSIMeanReversionStrategy(
        period=getattr(settings, "rsi_period", 14),
        oversold=Decimal(str(getattr(settings, "rsi_oversold", "30"))),
        overbought=Decimal(str(getattr(settings, "rsi_overbought", "70"))),
    )


register(IndicatorStrategy.name, _build_indicator)
register(EMACrossoverStrategy.name, _build_ema_crossover)
register(MACDCrossoverStrategy.name, _build_macd_crossover)
register(BollingerStrategy.name, _build_bollinger)
register(RSIMeanReversionStrategy.name, _build_rsi_reversion)


# ---- User-strategy auto-loading ----------------------------------------

def _load_user_strategies() -> None:
    """Auto-register any Strategy subclasses found in user_strategies/.

    Each module under ``user_strategies/`` is imported. Any class in
    those modules that subclasses :class:`Strategy` and exposes a
    unique ``name`` class attribute is registered using a builder that
    constructs it with the default constructor (no args).

    For strategies that need settings, users can override by either:
      * Accepting no arguments in ``__init__`` and reading from
        ``app.config.Settings`` inside ``generate_signal`` (not recommended
        — the signal interface is exchange-free, but reading settings is
        acceptable when the strategy is a singleton).
      * Defining a top-level ``build(settings)`` function in their module
        which the loader will use as the builder.
    """
    user_dir = Path(__file__).parent / "user_strategies"
    if not user_dir.is_dir():
        return
    for module_info in pkgutil.iter_modules([str(user_dir)]):
        module_name = f"app.strategy.user_strategies.{module_info.name}"
        try:
            module = importlib.import_module(module_name)
        except Exception as exc:  # noqa: BLE001 — user code, broad to keep app alive
            logger.error("failed to import user strategy module %s: %s", module_name, exc)
            continue
        # If the module exposes a build() function, use it directly.
        build_fn = getattr(module, "build", None)
        if callable(build_fn):
            # Prefer the class's ``name`` attribute — the file stem
            # (``_my_first_strategy``) may be a user-convention prefix
            # and not the desired strategy name.
            strategy_name: str | None = None
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (
                    isinstance(attr, type)
                    and issubclass(attr, Strategy)
                    and attr is not Strategy
                    and hasattr(attr, "name")
                ):
                    candidate_name = attr.name
                    if isinstance(candidate_name, str) and candidate_name:
                        strategy_name = candidate_name
                        break
            if strategy_name is None:
                strategy_name = getattr(module, "name", module_info.name)
            register(strategy_name, build_fn)
            continue
        # Otherwise, scan for Strategy subclasses with a `name` attribute.
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if isinstance(attr, type) and issubclass(attr, Strategy) and attr is not Strategy and hasattr(attr, "name"):
                name = attr.name
                if not isinstance(name, str) or not name:
                    continue
                register(name, lambda _settings, cls=attr: cls())

    # Also scan for files starting with an underscore — pkgutil's
    # iter_modules skips them by default, but the shipped example file
    # is intentionally prefixed to signal "user, please adapt me".
    for candidate in user_dir.glob("*.py"):
        if candidate.name == "__init__.py" or candidate.name.startswith("__"):
            continue
        module_name = f"app.strategy.user_strategies.{candidate.stem}"
        if module_name in sys.modules:
            continue
        spec = importlib.util.spec_from_file_location(module_name, candidate)
        if spec is None or spec.loader is None:
            continue
        try:
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)
        except Exception as exc:  # noqa: BLE001 — user code, broad to keep app alive
            logger.error("failed to import user strategy module %s: %s", module_name, exc)
            continue
        build_fn = getattr(module, "build", None)
        if callable(build_fn):
            # Prefer the class's ``name`` attribute if present — the
            # file's stem (e.g. ``_my_first_strategy``) may be a user
            # convention and not the desired strategy name.
            strategy_name: str | None = None
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (
                    isinstance(attr, type)
                    and issubclass(attr, Strategy)
                    and attr is not Strategy
                    and hasattr(attr, "name")
                ):
                    candidate_name = attr.name
                    if isinstance(candidate_name, str) and candidate_name:
                        strategy_name = candidate_name
                        break
            if strategy_name is None:
                strategy_name = getattr(module, "name", candidate.stem)
            register(strategy_name, build_fn)
        else:
            # Strategy-subclass logic mirroring the first loop. The strategy
            # name comes from the class's ``name`` attribute, not the file
            # stem (the file may be prefixed with ``_`` as a "user example"
            # convention).
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (
                    isinstance(attr, type)
                    and issubclass(attr, Strategy)
                    and attr is not Strategy
                    and hasattr(attr, "name")
                ):
                    name = attr.name
                    if isinstance(name, str) and name:
                        register(name, lambda _s, cls=attr: cls())


_load_user_strategies()


# ---- Factory -----------------------------------------------------------

def create_strategy(settings: Settings) -> Strategy:
    """Build the configured strategy.

    Raises :class:`ValueError` if ``STRATEGY`` does not match any
    registered strategy. The list of valid names is logged for the user.
    """
    name = settings.strategy
    builder = _REGISTRY.get(name)
    if builder is None:
        registered = ", ".join(available_strategies())
        raise ValueError(
            f"unsupported strategy: {name!r}. "
            f"Registered strategies: {registered}. "
            f"Add a custom strategy by dropping a Python file into "
            f"app/strategy/user_strategies/ — see docs/USER_STRATEGIES.md."
        )
    return builder(settings)
