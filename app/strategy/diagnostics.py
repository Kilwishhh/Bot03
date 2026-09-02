"""Runtime scanner diagnostics counters — used by the admin endpoint and
by the runtime worker for structured log lines.

Lifecycle:
- A single in-process instance is attached to StrategyScanner.
- Each scan_once() call resets the cycle counters and starts a new cycle.
- Aggregate counters (lifetime) are kept alongside the per-cycle counters.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class CycleDiagnostics:
    started_at: float
    finished_at: float | None = None
    strategy_id: str | None = None
    strategy_name: str | None = None
    timeframe: str | None = None
    universe_type: str | None = None
    symbols_loaded: int = 0
    symbols_evaluated: int = 0
    symbols_skipped: int = 0
    skip_reasons: dict[str, int] = field(default_factory=dict)
    symbols_with_candles: int = 0
    symbols_without_candles: int = 0
    fresh_candles: int = 0
    indicators_calculated: int = 0
    conditions_evaluated: int = 0
    conditions_passed: int = 0
    conditions_failed: int = 0
    signals_created: int = 0
    signals_persisted: int = 0
    signals_deduped: int = 0
    last_error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "duration_seconds": round((self.finished_at or time.time()) - self.started_at, 4),
            "strategy_id": self.strategy_id,
            "strategy_name": self.strategy_name,
            "timeframe": self.timeframe,
            "universe_type": self.universe_type,
            "symbols_loaded": self.symbols_loaded,
            "symbols_evaluated": self.symbols_evaluated,
            "symbols_skipped": self.symbols_skipped,
            "skip_reasons": dict(self.skip_reasons),
            "symbols_with_candles": self.symbols_with_candles,
            "symbols_without_candles": self.symbols_without_candles,
            "fresh_candles": self.fresh_candles,
            "indicators_calculated": self.indicators_calculated,
            "conditions_evaluated": self.conditions_evaluated,
            "conditions_passed": self.conditions_passed,
            "conditions_failed": self.conditions_failed,
            "signals_created": self.signals_created,
            "signals_persisted": self.signals_persisted,
            "signals_deduped": self.signals_deduped,
            "last_error": self.last_error,
        }


class ScannerDiagnostics:
    """Thread-safe counter set for the active strategy scanner."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._last_cycle: CycleDiagnostics | None = None
        self._cycles: list[CycleDiagnostics] = []
        self._max_history = 20
        self._running = False
        self._last_scan_at: float | None = None

    # ----- lifecycle -----

    def start_cycle(
        self,
        *,
        strategy_id: str | None = None,
        strategy_name: str | None = None,
        timeframe: str | None = None,
        universe_type: str | None = None,
    ) -> CycleDiagnostics:
        with self._lock:
            self._running = True
            self._last_scan_at = time.time()
            cycle = CycleDiagnostics(
                started_at=self._last_scan_at,
                strategy_id=strategy_id,
                strategy_name=strategy_name,
                timeframe=timeframe,
                universe_type=universe_type,
            )
            self._last_cycle = cycle
            return cycle

    def end_cycle(self) -> None:
        with self._lock:
            self._running = False
            if self._last_cycle is not None:
                self._last_cycle.finished_at = time.time()
                self._cycles.append(self._last_cycle)
                if len(self._cycles) > self._max_history:
                    self._cycles = self._cycles[-self._max_history:]

    # ----- per-symbol update -----

    def record_symbol_loaded(self) -> None:
        with self._lock:
            if self._last_cycle:
                self._last_cycle.symbols_loaded += 1

    def record_symbol_evaluated(self) -> None:
        with self._lock:
            if self._last_cycle:
                self._last_cycle.symbols_evaluated += 1

    def record_symbol_with_candles(self, fresh: bool) -> None:
        with self._lock:
            if self._last_cycle:
                self._last_cycle.symbols_with_candles += 1
                if fresh:
                    self._last_cycle.fresh_candles += 1

    def record_symbol_without_candles(self, reason: str) -> None:
        with self._lock:
            if self._last_cycle:
                self._last_cycle.symbols_without_candles += 1
                self._last_cycle.symbols_skipped += 1
                self._last_cycle.skip_reasons[reason] = (
                    self._last_cycle.skip_reasons.get(reason, 0) + 1
                )

    def record_indicator(self) -> None:
        with self._lock:
            if self._last_cycle:
                self._last_cycle.indicators_calculated += 1

    def record_conditions(self, passed: int, total: int) -> None:
        with self._lock:
            if self._last_cycle:
                self._last_cycle.conditions_evaluated += total
                self._last_cycle.conditions_passed += passed
                self._last_cycle.conditions_failed += (total - passed)

    def record_signal_created(self) -> None:
        with self._lock:
            if self._last_cycle:
                self._last_cycle.signals_created += 1

    def record_signal_persisted(self) -> None:
        with self._lock:
            if self._last_cycle:
                self._last_cycle.signals_persisted += 1

    def record_signal_deduped(self) -> None:
        with self._lock:
            if self._last_cycle:
                self._last_cycle.signals_deduped += 1

    def record_error(self, error: str) -> None:
        with self._lock:
            if self._last_cycle:
                self._last_cycle.last_error = error

    # ----- read-only summary -----

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            current = self._last_cycle.to_dict() if self._last_cycle else None
            cycles = [c.to_dict() for c in self._cycles[-5:]]
            total_signals = sum(c.signals_persisted for c in self._cycles)
            return {
                "running": self._running,
                "last_scan_at": self._last_scan_at,
                "last_cycle": current,
                "recent_cycles": cycles,
                "total_signals_persisted": total_signals,
            }
