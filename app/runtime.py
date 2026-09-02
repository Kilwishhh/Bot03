"""One exchange-neutral trading cycle."""

import logging
import time
from decimal import Decimal

from app.database import TradingRepository
from app.execution import OrderManager
from app.market_data import MarketDataProvider
from app.notifications import SignalPublisher
from app.signals import SignalEngine

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Multi-symbol scanner runner (the actual bot worker)
# ---------------------------------------------------------------------------

class MultiSymbolRunner:
    """Run the multi-strategy scanner across all active strategies and universes.

    This replaces the single-symbol BotRunner for the new architecture.
    """

    def __init__(
        self,
        scanner,
        interval_seconds: float = 60.0,
        alerts=None,
    ) -> None:
        if interval_seconds <= 0:
            raise ValueError("interval must be positive")
        self._scanner = scanner
        self._interval_seconds = interval_seconds
        self._stop_requested = False
        self._paused = False
        self._alerts = alerts

    def stop(self) -> None:
        self._stop_requested = True

    def pause(self) -> None:
        self._paused = True

    def resume(self) -> None:
        self._paused = False

    @property
    def is_paused(self) -> bool:
        return self._paused

    def run(self, max_cycles: int | None = None) -> int:
        """Run the scanner loop. Returns number of cycles completed."""
        completed = 0
        while not self._stop_requested and (max_cycles is None or completed < max_cycles):
            # Wait while paused
            while self._paused and not self._stop_requested:
                time.sleep(0.2)
            if self._stop_requested:
                break

            cycle_done = False
            try:
                signals = self._scanner.scan_once()
                cycle_done = True
                if self._alerts is not None:
                    self._alerts.record_cycle_success()
                logger.info(
                    "SCAN_COMPLETED cycles=%d signals=%d stats=%s",
                    completed + 1, len(signals), self._scanner.stats,
                )
            except Exception as exc:
                logger.exception("scan cycle failed: %s", exc)
                if self._alerts is not None:
                    self._alerts.record_cycle_failure(exc)

            completed += 1

            # Sleep in chunks so stop is responsive. 0.2s chunks give sub-second stop latency.
            if not self._stop_requested and (max_cycles is None or completed < max_cycles):
                elapsed = 0
                chunk = 0.2
                while elapsed < self._interval_seconds and not self._stop_requested:
                    time.sleep(min(chunk, self._interval_seconds - elapsed))
                    elapsed += chunk

        return completed


class TradingCycle:
    def __init__(
        self,
        market_data: MarketDataProvider,
        signals: SignalEngine,
        orders: OrderManager,
        repository: TradingRepository,
        publisher: SignalPublisher | None = None,
        leverage: int = 1,
        position_notional: Decimal | None = None,
    ) -> None:
        self._market_data = market_data
        self._signals = signals
        self._orders = orders
        self._repository = repository
        self._publisher = publisher
        self._leverage = leverage
        self._position_notional = position_notional

    def run_once(self, symbol: str, timeframe: str, limit: int = 200):
        candles = self._market_data.candles(symbol, timeframe, limit)
        signal = self._signals.generate(symbol, candles)
        self._repository.save_signal(signal)
        if self._publisher is not None:
            try:
                self._publisher.publish(signal)
            except Exception as error:
                logger.warning("signal publication failed: %s", error)
                self._repository.record_error("notification", str(error))
        result = self._orders.process_signal(
            signal,
            daily_pnl=Decimal("0"),
            open_positions=0,
            leverage=self._leverage,
            position_notional=self._position_notional,
        )
        if result is not None:
            self._repository.save_order(result)
            self._repository.save_balance(self._orders.balance())
            self._repository.save_position(self._orders.position(symbol))
        self._repository.record_event("cycle_completed", f"{symbol} {signal.side.value}")
        return signal, result

    def record_error(self, error: Exception) -> None:
        self._repository.record_error("cycle", str(error))


class BotRunner:
    """Run trading cycles until stopped, with bounded error recovery."""

    def __init__(self, cycle: TradingCycle, symbol: str, timeframe: str, interval_seconds: float = 60.0, alerts=None) -> None:
        if interval_seconds <= 0:
            raise ValueError("interval must be positive")
        self._cycle = cycle
        self._symbol = symbol
        self._timeframe = timeframe
        self._interval_seconds = interval_seconds
        self._stop_requested = False
        self._paused = False
        self._alerts = alerts

    def stop(self) -> None:
        self._stop_requested = True

    def pause(self) -> None:
        self._paused = True

    def resume(self) -> None:
        self._paused = False

    @property
    def is_paused(self) -> bool:
        return self._paused

    def run(self, max_cycles: int | None = None) -> int:
        completed = 0
        while not self._stop_requested and (max_cycles is None or completed < max_cycles):
            # Wait while paused (wake on resume or stop)
            while self._paused and not self._stop_requested:
                import time as _time
                _time.sleep(0.5)
            if self._stop_requested:
                break
            try:
                self._cycle.run_once(self._symbol, self._timeframe)
                completed += 1
                if self._alerts is not None:
                    self._alerts.record_cycle_success()
            except Exception as error:
                logger.exception("trading cycle failed: %s", error)
                self._cycle.record_error(error)
                if self._alerts is not None:
                    self._alerts.record_cycle_failure(error)
                completed += 1
            if not self._stop_requested and (max_cycles is None or completed < max_cycles):
                elapsed = 0
                while elapsed < self._interval_seconds and not self._stop_requested:
                    time.sleep(min(1.0, self._interval_seconds - elapsed))
                    elapsed += 1
        return completed
