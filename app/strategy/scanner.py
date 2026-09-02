"""Multi-symbol strategy scanner.

Replaces the BTCUSDT-only behavior. Reads strategies from the database,
resolves their universe to a list of symbols, fetches candles for each,
computes indicators, evaluates entry conditions, and creates signals.

Pipeline stages (each logged at the appropriate level):
  [SCAN]    strategy load, universe resolution
  [DATA]    candle fetch, freshness check
  [EVAL]    indicator computation, condition evaluation
  [SIGNAL]  signal creation, dedup, persistence, publication
"""
from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from app.database import TradingRepository
from app.exchange.models import Candle
from app.market_data.base import MarketDataProvider
from app.strategy.condition_engine import (
    evaluate_condition_groups,
    evaluate_condition_groups_with_results,
    validate_condition_config,
)
from app.strategy.indicators import compute_indicators, get_timeframe_minutes, price as price_indicator
from app.strategy.universe import get_symbols_for_universe

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Binance native kline intervals — everything else must be aggregated from 1m
# ---------------------------------------------------------------------------

_NATIVE_BINANCE_INTERVALS = frozenset({
    "1m", "3m", "5m", "15m", "30m",
    "1h", "2h", "4h", "6h", "8h", "12h",
    "1d", "3d", "1w", "1M",
})


def _aggregate_candles(raw: list[Candle], target_minutes: int) -> list[Candle]:
    """Aggregate raw 1m candles into buckets of `target_minutes` each.

    Each bucket produces one Candle: open=first.open, high=max(highs),
    low=min(lows), close=last.close, volume=sum(volumes),
    open_time=bucket_start, close_time=bucket_end.
    """
    if not raw or target_minutes <= 0:
        return []

    from datetime import timedelta
    sorted_raw = sorted(raw, key=lambda c: c.open_time)
    buckets: list[Candle] = []
    bucket: list[Candle] = [sorted_raw[0]]

    for c in sorted_raw[1:]:
        bucket_start = bucket[0].open_time
        elapsed_minutes = int((c.open_time - bucket_start).total_seconds() // 60)
        if elapsed_minutes >= target_minutes:
            buckets.append(_make_agg_candle(bucket))
            bucket = [c]
        else:
            bucket.append(c)

    if bucket:
        buckets.append(_make_agg_candle(bucket))

    return buckets


def _make_agg_candle(group: list[Candle]) -> Candle:
    """Build a single aggregated Candle from a list of raw candles."""
    return Candle(
        open_time=group[0].open_time,
        close_time=group[-1].close_time,
        open=group[0].open,
        high=max(c.high for c in group),
        low=min(c.low for c in group),
        close=group[-1].close,
        volume=sum(c.volume for c in group),
    )


def _get_candles_for_timeframe(
    market_data: MarketDataProvider,
    symbol: str,
    timeframe: str,
    limit: int = 200,
) -> list[Candle]:
    """Fetch candles for a timeframe, aggregating from 1m for non-native intervals."""
    if timeframe in _NATIVE_BINANCE_INTERVALS:
        return market_data.candles(symbol, timeframe, limit=limit)

    minutes = get_timeframe_minutes(timeframe)
    # Fetch enough 1m candles to cover `limit` aggregated bars
    raw = market_data.candles(symbol, "1m", limit=max(limit * minutes, limit))
    return _aggregate_candles(raw, minutes)


def _candle_age_seconds(candle: Candle, now: datetime | None = None) -> float:
    """Age of a candle's close_time in seconds relative to UTC now.

    Binance semantics: close_time is EXCLUSIVE end of the interval.
    A candle is CLOSED when now >= close_time (age >= 0).
    A candle is IN-PROGRESS when now < close_time (age < 0).

    `now` is injectable for testing. Defaults to datetime.now(UTC).
    """
    if now is None:
        now = datetime.now(UTC)
    ct = candle.close_time
    if ct.tzinfo is None:
        ct = ct.replace(tzinfo=UTC)
    return (now - ct).total_seconds()


def _is_candle_closed(candle: Candle, now: datetime | None = None) -> bool:
    """True if candle's close_time has been reached.

    Binance close_time is the exclusive end of the interval. The candle
    is closed once `now >= close_time` (age >= 0).
    """
    if now is None:
        now = datetime.now(UTC)
    ct = candle.close_time
    if ct.tzinfo is None:
        ct = ct.replace(tzinfo=UTC)
    return now >= ct


def _select_last_closed_candle(
    candles: list[Candle], now: datetime | None = None
) -> Candle | None:
    """Return the most recent candle whose close_time has been reached.

    Walks the list backwards. Returns None if no closed candle exists.
    Skips in-progress (close_time > now) and future candles.

    P0-02: enforces closed-candle evaluation.
    """
    if not candles:
        return None
    if now is None:
        now = datetime.now(UTC)
    # Candles should be in ascending open_time order. Walk from the end.
    for c in reversed(candles):
        ct = c.close_time
        if ct.tzinfo is None:
            ct = ct.replace(tzinfo=UTC)
        if now >= ct:
            return c
    return None


# ---------------------------------------------------------------------------
# Strategy runtime config
# ---------------------------------------------------------------------------

@dataclass
class StrategyRuntime:
    """Loaded strategy config + a few derived fields."""
    id: str
    name: str
    user_id: str
    description: str
    lifecycle_state: str
    execution_mode: str
    market: str
    timeframe: str
    universe_type: str
    universe_config: dict[str, Any]
    indicators_config: list[dict]
    conditions_config: dict[str, Any]
    exit_config: dict[str, Any]
    risk_config: dict[str, Any]
    confidence_config: dict[str, Any]
    filters_config: dict[str, Any]
    notes: str | None
    is_system_diagnostic: bool = False

    @property
    def is_active(self) -> bool:
        return self.lifecycle_state in ("paper", "testnet", "live")

    @property
    def is_paused(self) -> bool:
        return self.lifecycle_state == "paused"


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

def load_active_strategies(repo: TradingRepository) -> list[StrategyRuntime]:
    """Load strategies eligible for runtime evaluation.

    Active states: paper, testnet, live.
    Skips draft, backtest, paused, stopped, disabled.
    """
    conn = repo.db
    try:
        rows = conn.execute(
            "SELECT * FROM strategies WHERE lifecycle_state IN ('paper','testnet','live')"
        ).fetchall()
    except sqlite3.OperationalError:
        return []

    results: list[StrategyRuntime] = []
    for row in rows:
        try:
            r = _row_to_runtime(conn, row)
            if r is not None:
                results.append(r)
        except Exception as exc:
            logger.warning("failed to load strategy row: %s", exc)
    return results


_PRAGMA_CACHE: dict[int, dict[str, int]] = {}


def _named_row(conn: sqlite3.Connection, table: str) -> dict[str, int]:
    """Return a {col_name: 0based_index} map for `table`, caching by conn id."""
    key = id(conn)
    if key not in _PRAGMA_CACHE:
        _PRAGMA_CACHE[key] = {
            r[1]: r[0] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()
        }
    return _PRAGMA_CACHE[key]


def _row_to_runtime(conn: sqlite3.Connection, row: tuple) -> StrategyRuntime | None:
    """Map strategies table row → StrategyRuntime.

    Uses PRAGMA to resolve column positions by name, so it works regardless
    of which optional columns are present.
    """
    cols = _named_row(conn, "strategies")

    def _v(key: str) -> Any:
        idx = cols.get(key)
        return row[idx] if idx is not None and idx < len(row) else None

    def _s(key: str) -> str | None:
        v = _v(key)
        if v is None:
            return None
        return v if isinstance(v, str) else str(v)

    def _j(key: str, default=None) -> Any:
        raw = _v(key)
        if not raw:
            return default if default is not None else {}
        if isinstance(raw, (dict, list)):
            return raw
        try:
            return json.loads(raw)
        except (TypeError, ValueError):
            return default if default is not None else {}

    try:
        strat_name = _s("name") or "?"
        return StrategyRuntime(
            id=_v("id") or "?",
            user_id=_v("user_id") or "?",
            name=strat_name,
            description=_s("description") or "",
            lifecycle_state=_s("lifecycle_state") or "draft",
            execution_mode=_s("execution_mode") or "paper",
            market=_s("market") or "",
            timeframe=_s("timeframe") or "1m",
            universe_type=_s("universe_type") or "all_binance_futures",
            universe_config=_j("universe_config"),
            indicators_config=_j("indicators_config", []),
            conditions_config=_j("conditions_config", {}),
            exit_config=_j("exit_config", {}),
            risk_config=_j("risk_config", {}),
            confidence_config=_j("confidence_config", {}),
            filters_config=_j("filters_config", {}),
            notes=_s("notes"),
            is_system_diagnostic=strat_name == "SIGNAL_PIPELINE_TEST",
        )
    except Exception as exc:
        logger.warning("could not parse strategy row: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Signal creation
# ---------------------------------------------------------------------------

@dataclass
class ScannerSignal:
    strategy_id: str
    strategy_name: str
    user_id: str  # owner — copied from strategy.user_id
    symbol: str
    side: str          # "BUY" or "SELL"
    timeframe: str
    entry: float
    take_profit: float
    stop_loss: float
    confidence: float
    mode: str
    reasons: list[str]
    indicators: dict[str, Any]
    candle_close_time: str
    candle_age_seconds: float
    confidence_hits: int = 0
    confidence_total: int = 0


def _compute_tp_sl(
    entry: float, side: str,
    exit_config: dict,
) -> tuple[float, float]:
    """Compute take-profit and stop-loss from config percentages."""
    tp_pct = float(exit_config.get("take_profit_pct", exit_config.get("tp1_pct", 1.0))) / 100.0
    sl_pct = float(exit_config.get("stop_loss_pct", 0.5)) / 100.0

    if side == "BUY":
        tp = entry * (1 + tp_pct)
        sl = entry * (1 - sl_pct)
    else:
        tp = entry * (1 - tp_pct)
        sl = entry * (1 + sl_pct)
    return tp, sl


def _compute_confidence(
    reasons_matched: int,
    total_conditions: int,
    confidence_config: dict,
) -> float:
    """Compute signal confidence based on conditions matched and config."""
    mode = confidence_config.get("mode", "automatic")
    if mode == "fixed":
        return float(confidence_config.get("min_confidence", 0.65))

    base = float(confidence_config.get("base_confidence", 0.5))
    if total_conditions == 0:
        return base
    ratio = min(1.0, reasons_matched / total_conditions)
    return round(base + (0.95 - base) * ratio, 4)


def _determine_side(reasons: list[str], conditions_config: dict) -> str:
    """Decide BUY or SELL based on condition reason text and config."""
    direction = (conditions_config.get("direction") or "BUY").upper()
    if direction in ("BUY", "LONG"):
        return "BUY"
    return "SELL"


# ---------------------------------------------------------------------------
# Scanner with diagnostics
# ---------------------------------------------------------------------------

from app.strategy.diagnostics import ScannerDiagnostics


class StrategyScanner:
    """Scans all active strategies across their universes with full diagnostics.

    Uses the existing market_data provider to fetch candles per symbol.
    Each scan cycle emits structured log lines at INFO/DEBUG level for every
    pipeline stage so the exact failure point is always identifiable.
    """

    def __init__(
        self,
        repo: TradingRepository,
        market_data: MarketDataProvider,
        minimum_hits: int = 1,
    ) -> None:
        self._repo = repo
        self._market_data = market_data
        self._lock = threading.RLock()
        # Minimum number of conditions that must pass for a signal to be emitted.
        # Loaded from paper_config.json — can be 1+ (any pass) or N (strict).
        self._minimum_hits = max(1, int(minimum_hits))
        # Dedup set: (strategy_id, symbol, candle_close_time_epoch) — one signal per candle
        self._seen: set[tuple[str, str, int]] = set()
        self._max_seen = 5000
        self._diag = ScannerDiagnostics()
        # Lifetime aggregate stats (diagnostics resets per cycle)
        self._stats = {
            "strategies_loaded": 0,
            "symbols_scanned": 0,
            "indicators_calculated": 0,
            "signals_created": 0,
            "signals_persisted": 0,
            "last_scan": None,
        }

    @property
    def diagnostics(self) -> ScannerDiagnostics:
        return self._diag

    @property
    def stats(self) -> dict:
        return dict(self._stats)

    def scan_once(self) -> list[ScannerSignal]:
        """Run one full scan cycle. Returns list of generated signals."""
        signals: list[ScannerSignal] = []
        strategies = load_active_strategies(self._repo)
        self._stats["strategies_loaded"] = len(strategies)
        scan_time = datetime.now(UTC).isoformat()
        self._stats["last_scan"] = scan_time

        logger.info(
            "[SCAN] scan_started strategies_loaded=%d scan_time=%s",
            len(strategies), scan_time,
        )

        for strat in strategies:
            diag = self._diag.start_cycle(
                strategy_id=strat.id,
                strategy_name=strat.name,
                timeframe=strat.timeframe,
                universe_type=strat.universe_type,
            )
            try:
                sigs = self._scan_strategy(strat)
                signals.extend(sigs)
            except Exception as exc:
                logger.exception("strategy %s scan FAILED: %s", strat.name, exc)
                self._diag.record_error(str(exc))
            finally:
                self._diag.end_cycle()
                # Log cycle summary at INFO
                c = self._diag.snapshot()["last_cycle"]
                if c:
                    logger.info(
                        "[SCAN] strategy=%s symbols_loaded=%d symbols_evaluated=%d "
                        "symbols_with_candles=%d fresh_candles=%d "
                        "indicators_calculated=%d conditions_passed=%d "
                        "signals_created=%d signals_persisted=%d signals_deduped=%d "
                        "duration_ms=%.1f last_error=%s",
                        strat.name,
                        c["symbols_loaded"], c["symbols_evaluated"],
                        c["symbols_with_candles"], c["fresh_candles"],
                        c["indicators_calculated"], c["conditions_passed"],
                        c["signals_created"], c["signals_persisted"], c["signals_deduped"],
                        c["duration_seconds"] * 1000,
                        c["last_error"],
                    )

        total_syms = sum(
            len(get_symbols_for_universe(s.universe_type, s.universe_config))
            for s in strategies
        )
        self._stats["symbols_scanned"] = total_syms
        logger.info(
            "[SCAN] scan_completed strategies=%d total_symbols=%d signals=%d",
            len(strategies), total_syms, len(signals),
        )
        return signals

    def _scan_strategy(self, strat: StrategyRuntime) -> list[ScannerSignal]:
        """Scan a single strategy across its universe."""
        # Validate config before scanning
        cond_errors = validate_condition_config(strat.conditions_config)
        if cond_errors:
            logger.warning(
                "strategy %s has INVALID conditions: %s", strat.name, cond_errors
            )
            self._diag.record_error("invalid_conditions:" + ";".join(cond_errors))
            return []

        # Resolve universe
        try:
            symbols = get_symbols_for_universe(
                strat.universe_type,
                strat.universe_config,
                use_testnet=(strat.execution_mode == "testnet"),
            )
        except Exception as exc:
            logger.error(
                "[SCAN] strategy=%s UNIVERSE_RESOLUTION_FAILED error=%s",
                strat.name, exc,
            )
            self._diag.record_error(f"universe_resolution:{exc}")
            return []

        if not symbols:
            logger.warning("[SCAN] strategy=%s UNIVERSE_EMPTY universe_type=%s",
                           strat.name, strat.universe_type)
            return []

        logger.info(
            "[SCAN] strategy=%s universe_type=%s universe_size=%d",
            strat.name, strat.universe_type, len(symbols),
        )

        signals: list[ScannerSignal] = []
        for symbol in symbols:
            self._diag.record_symbol_loaded()
            try:
                sig = self._scan_symbol(strat, symbol)
                if sig is not None:
                    signals.append(sig)
            except Exception as exc:
                logger.warning(
                    "[DATA] strategy=%s symbol=%s SCAN_FAILED: %s",
                    strat.name, symbol, exc,
                )
                self._diag.record_symbol_without_candles(str(exc))
                continue

        return signals

    def _scan_symbol(
        self, strat: StrategyRuntime, symbol: str
    ) -> ScannerSignal | None:
        """Scan one strategy against one symbol. Returns signal or None."""
        self._diag.record_symbol_evaluated()

        # Fetch candles (handles aggregation for non-native timeframes)
        try:
            candles = _get_candles_for_timeframe(
                self._market_data, symbol, strat.timeframe, 200
            )
        except Exception as exc:
            logger.debug(
                "[DATA] strategy=%s symbol=%s NO_CANDLES error=%s",
                strat.name, symbol, exc,
            )
            self._diag.record_symbol_without_candles("fetch_error")
            return None

        if not candles:
            logger.debug(
                "[DATA] strategy=%s symbol=%s NO_CANDLES (empty list)",
                strat.name, symbol,
            )
            self._diag.record_symbol_without_candles("empty")
            return None

        if len(candles) < 30:
            logger.debug(
                "[DATA] strategy=%s symbol=%s INSUFFICIENT_HISTORY candles=%d need=30",
                strat.name, symbol, len(candles),
            )
            self._diag.record_symbol_without_candles("insufficient_history")
            return None

        # P0-02: select the latest CLOSED candle. Binance close_time is EXCLUSIVE,
        # so candles[-1] is often the in-progress candle whose age is negative.
        # We must not evaluate a still-forming candle.
        latest_candle = _select_last_closed_candle(candles)
        if latest_candle is None:
            logger.debug(
                "[DATA] strategy=%s symbol=%s NO_CLOSED_CANDLE "
                "all_candles_in_progress_or_future",
                strat.name, symbol,
            )
            self._diag.record_symbol_without_candles("no_closed_candle")
            return None

        # P0-03: enforce non-negative age. If a closed candle somehow has
        # negative age (clock skew, wrong data), skip it.
        age = _candle_age_seconds(latest_candle)
        if age < 0:
            logger.debug(
                "[DATA] strategy=%s symbol=%s INVALID_AGE age=%.1fs "
                "— skipping (clock skew or bad data)",
                strat.name, symbol, age,
            )
            self._diag.record_symbol_without_candles("invalid_age")
            return None

        # Freshness check: the closed candle must be recent.
        is_fresh = age < 300  # 5 minutes

        self._diag.record_symbol_with_candles(is_fresh)

        if not is_fresh:
            logger.debug(
                "[DATA] strategy=%s symbol=%s STALE_CANDLE age_seconds=%.1f "
                "candle_close=%s max_age=300",
                strat.name, symbol, age, latest_candle.close_time,
            )
            return None

        # Log candle metadata for 1m timeframe
        if strat.timeframe == "1m":
            logger.debug(
                "[DATA] strategy=%s symbol=%s timeframe=%s candle_count=%d "
                "configured_tf=%s actual_tf=%s candle_close=%s candle_age=%.1fs",
                strat.name, symbol, strat.timeframe, len(candles),
                strat.timeframe, strat.timeframe,
                latest_candle.close_time, age,
            )

        # Compute indicators
        try:
            values = compute_indicators(candles, strat.indicators_config)
            if len(candles) > 1:
                prev_values = compute_indicators(candles[:-1], strat.indicators_config)
            else:
                prev_values = {}
        except Exception as exc:
            logger.warning(
                "[EVAL] strategy=%s symbol=%s INDICATOR_ERROR: %s",
                strat.name, symbol, exc,
            )
            return None

        self._diag.record_indicator()

        # Evaluate entry conditions
        matched, reasons, cond_results = evaluate_condition_groups_with_results(
            strat.conditions_config, values, prev_values
        )

        total_conds = _count_conditions(strat.conditions_config)
        hits = sum(1 for c in cond_results if c.passed)
        self._diag.record_conditions(hits, max(1, total_conds))

        if not matched:
            logger.debug(
                "[EVAL] strategy=%s symbol=%s CONDITIONS_FAILED reasons=%s",
                strat.name, symbol, reasons,
            )
            return None

        # P0-02: enforce minimum_hits threshold from paper config
        if hits < self._minimum_hits:
            logger.debug(
                "[EVAL] strategy=%s symbol=%s MINIMUM_HITS_NOT_MET "
                "hits=%d required=%d — signal suppressed",
                strat.name, symbol, hits, self._minimum_hits,
            )
            return None

        # Get entry price
        entry = values.get("PRICE")
        if entry is None:
            logger.debug(
                "[EVAL] strategy=%s symbol=%s NO_PRICE_INDICATOR",
                strat.name, symbol,
            )
            return None

        # Deduplicate on (strategy, symbol, candle_close_time epoch)
        candle_time = candles[-1].close_time
        dedup_epoch = int(candle_time.timestamp())
        dedup_key = (strat.id, symbol, dedup_epoch)
        with self._lock:
            if dedup_key in self._seen:
                logger.debug(
                    "[SIGNAL] strategy=%s symbol=%s DEDUPED candle_time=%s",
                    strat.name, symbol, candle_time,
                )
                self._diag.record_signal_deduped()
                return None
            self._seen.add(dedup_key)
            if len(self._seen) > self._max_seen:
                drop_n = self._max_seen // 2
                self._seen = set(list(self._seen)[drop_n:])

        side = _determine_side(reasons, strat.conditions_config)
        tp, sl = _compute_tp_sl(entry, side, strat.exit_config)
        confidence = _compute_confidence(
            len(reasons), total_conds, strat.confidence_config
        )

        signal = ScannerSignal(
            strategy_id=strat.id,
            strategy_name=strat.name,
            user_id=strat.user_id,
            symbol=symbol,
            side=side,
            timeframe=strat.timeframe,
            entry=entry,
            take_profit=tp,
            stop_loss=sl,
            confidence=confidence,
            mode=strat.execution_mode,
            reasons=reasons,
            indicators=values,
            candle_close_time=str(candle_time),
            candle_age_seconds=age,
            confidence_hits=hits,
            confidence_total=total_conds,
        )

        self._diag.record_signal_created()
        self._save_signal(signal)
        self._stats["signals_created"] += 1

        logger.info(
            "[SIGNAL] strategy=%s symbol=%s side=%s entry=%.6f tp=%.6f sl=%.6f "
            "confidence=%.4f candle_age=%.1fs reasons=%s",
            strat.name, symbol, side, entry, tp, sl, confidence,
            age, "; ".join(reasons),
        )

        return signal

    def _save_signal(self, sig: ScannerSignal) -> None:
        """Persist signal to the signals table."""
        conn = self._repo.db
        try:
            cols = [r[1] for r in conn.execute("PRAGMA table_info(signals)").fetchall()]
        except Exception:
            cols = []

        # Determine if we have the new extended schema
        has_signal_id = "signal_id" in cols
        has_mode = "mode" in cols

        try:
            if has_signal_id:
                signal_id = str(uuid.uuid4())
                row = {
                    "id": signal_id,  # back-compat: SignalService uses `id`
                    "signal_id": signal_id,
                    "user_id": sig.user_id,  # critical for SignalService.list()
                    "strategy_id": sig.strategy_id,
                    "strategy_name": sig.strategy_name,
                    "symbol": sig.symbol,
                    "side": sig.side,
                    "timeframe": sig.timeframe,
                    "entry": sig.entry,
                    "entry_price": str(sig.entry),  # back-compat with old schema
                    "take_profit": sig.take_profit,
                    "stop_loss": sig.stop_loss,
                    "confidence": sig.confidence,
                    "confidence_hits": sig.confidence_hits,
                    "confidence_total": sig.confidence_total,
                    "mode": sig.mode,
                    "reasons": "; ".join(sig.reasons),
                    "reason": "; ".join(sig.reasons),  # back-compat column
                    "indicators": json.dumps(sig.indicators, default=str),
                    "candle_close_time": sig.candle_close_time,
                    "status": "CREATED",
                    "signal_status": "active",
                    "trading_status": "pending",
                    "telegram_status": "pending",
                    "square_status": "pending",
                    "created_at": datetime.now(UTC).isoformat(),
                    "updated_at": datetime.now(UTC).isoformat(),
                    "timestamp": datetime.now(UTC).isoformat(),
                }
                row = {k: v for k, v in row.items() if k in cols}
                if not row:
                    return
                placeholders = ", ".join("?" for _ in row)
                col_list = ", ".join(row)
                conn.execute(
                    f"INSERT INTO signals ({col_list}) VALUES ({placeholders})",
                    tuple(row.values()),
                )
            else:
                # Legacy 6-column signals table — extend if confidence_hits/total columns exist
                has_conf_hits = "confidence_hits" in cols
                has_mode = "mode" in cols
                row_vals = [sig.symbol, sig.side, sig.confidence,
                            datetime.now(UTC).isoformat(), sig.strategy_name,
                            "; ".join(sig.reasons)]
                row_cols = ["symbol", "side", "confidence", "timestamp", "strategy", "reason"]
                if has_conf_hits:
                    row_cols += ["confidence_hits", "confidence_total"]
                    row_vals += [sig.confidence_hits, sig.confidence_total]
                if has_mode:
                    row_cols.append("mode")
                    row_vals.append(sig.mode)
                conn.execute(
                    f"INSERT INTO signals ({', '.join(row_cols)}) VALUES ({', '.join('?' * len(row_cols))})",
                    tuple(row_vals),
                )
            self._diag.record_signal_persisted()
            self._stats["signals_persisted"] += 1
        except Exception as exc:
            logger.warning("[SIGNAL] PERSISTENCE_FAILED for %s/%s: %s",
                           sig.strategy_name, sig.symbol, exc)
            self._diag.record_error(f"persistence:{exc}")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _count_conditions(config: dict) -> int:
    """Recursively count leaf conditions in a condition config."""
    count = 0
    for grp in config.get("groups", []):
        count += len(grp.get("conditions", []))
    return count
