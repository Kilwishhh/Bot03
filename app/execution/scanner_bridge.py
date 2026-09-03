"""ScannerExecutionBridge: wire scanner signals into the real execution pipeline.

Pipeline (one scanner signal at a time):

  ScannerSignal
    → to_execution_request
    → DB dedup check (strategy_id, symbol, candle_close_epoch)
    → RiskManager.approve (real risk engine, real reasons)
    → OrderManager.process_signal (real OrderManager, real PositionManager)
    → Place TP/SL conditional orders on the adapter
    → Persist: orders, position, balance, trade
    → Update signal.trading_status to "EXECUTED" / "REJECTED"
    → Record execution event

Reuses existing RiskManager / OrderManager / PositionManager / PaperTradingAdapter
— no parallel execution engine, no duplicate sizing logic.
"""
from __future__ import annotations

import json
import logging
import sqlite3
import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from app.database import TradingRepository
from app.exchange.models import (
    OrderRequest,
    OrderSide,
    OrderType,
    OrderResult,
    Position,
)
from app.execution.order_manager import OrderManager
from app.execution.signal_adapter import ExecutionRequest, to_execution_request
from app.risk import RiskManager
from app.strategy.scanner import ScannerSignal

logger = logging.getLogger(__name__)


# ── execution decision recording ────────────────────────────────────────


@dataclass
class ExecutionDecision:
    signal_strategy_id: str
    signal_symbol: str
    signal_candle_epoch: int
    side: str
    accepted: bool
    risk_reason: str | None = None
    order_id: str | None = None
    position_id: str | None = None
    tp_order_id: str | None = None
    sl_order_id: str | None = None
    quantity: str | None = None
    entry_price: str | None = None
    rejection_stage: str | None = None   # "dedup" | "risk" | "order" | "sizing" | "mode"


@dataclass
class BridgeStats:
    signals_processed: int = 0
    signals_deduped_db: int = 0
    signals_risk_rejected: int = 0
    signals_executed: int = 0
    signals_sizing_rejected: int = 0
    signals_wrong_mode: int = 0
    last_decisions: list[ExecutionDecision] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        d = {
            "signals_processed": self.signals_processed,
            "signals_deduped_db": self.signals_deduped_db,
            "signals_risk_rejected": self.signals_risk_rejected,
            "signals_executed": self.signals_executed,
            "signals_sizing_rejected": self.signals_sizing_rejected,
            "signals_wrong_mode": self.signals_wrong_mode,
        }
        return d


# ── DB-level dedup ───────────────────────────────────────────────────────


def _has_signal_dedup_index(conn: sqlite3.Connection) -> bool:
    try:
        rows = conn.execute("PRAGMA index_list(signals)").fetchall()
        for r in rows:
            # r[1] is index name
            if r[1] == "uniq_signals_dedup":
                return True
    except Exception:
        pass
    return False


def _ensure_signal_dedup_index(conn: sqlite3.Connection) -> None:
    """Create the unique index that protects against duplicate execution
    of the same (strategy_id, symbol, candle_close_time_epoch) signal.

    A new table column `candle_close_epoch` may not exist; we add it
    lazily and backfill scanner-written signals.
    """
    cols = [r[1] for r in conn.execute("PRAGMA table_info(signals)").fetchall()]
    if "candle_close_epoch" not in cols:
        conn.execute(
            "ALTER TABLE signals ADD COLUMN candle_close_epoch INTEGER"
        )
    # Backfill from the text candle_close_time column where present
    if "candle_close_time" in cols:
        conn.execute(
            "UPDATE signals SET candle_close_epoch = CAST(strftime('%s', candle_close_time) AS INTEGER) "
            "WHERE candle_close_epoch IS NULL AND candle_close_time IS NOT NULL"
        )
    if not _has_signal_dedup_index(conn):
        # Only create the index if every existing row has a non-null epoch
        # (NULL values are allowed by SQLite UNIQUE — multiple NULLs are
        # always considered distinct, so legacy NULL rows do not break
        # the constraint).
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS uniq_signals_dedup "
            "ON signals (strategy_id, symbol, candle_close_epoch) "
            "WHERE strategy_id IS NOT NULL AND symbol IS NOT NULL AND candle_close_epoch IS NOT NULL"
        )


# ── the bridge itself ────────────────────────────────────────────────────


class ScannerExecutionBridge:
    """Execute scanner-generated signals through the real pipeline.

    Construction-time responsibilities:
      - Validate execution mode (paper/testnet/live)
      - Build or accept an OrderManager
      - Reuse the existing repository (no second DB connection)

    Runtime responsibilities (called per cycle from MultiSymbolRunner):
      - Drain `signals` returned by the scanner
      - For each eligible signal: dedup → risk → order → persist
      - Publish execution events via the same notification path
    """

    ALLOWED_MODES = ("paper", "testnet", "live")

    def __init__(
        self,
        repo: TradingRepository,
        order_manager: OrderManager,
        risk: RiskManager,
        execution_mode: str,
        paper_position_notional: Decimal,
        leverage: int,
    ) -> None:
        if execution_mode not in self.ALLOWED_MODES:
            raise ValueError(
                f"execution_mode must be one of {self.ALLOWED_MODES}, got {execution_mode!r}"
            )
        if execution_mode == "live":
            raise ValueError("live trading is not permitted in this task")

        self._repo = repo
        self._orders = order_manager
        self._risk = risk
        self._mode = execution_mode
        self._paper_position_notional = Decimal(str(paper_position_notional))
        self._leverage = int(leverage)
        self._lock = threading.RLock()
        self._stats = BridgeStats()
        # DB-level dedup index
        try:
            _ensure_signal_dedup_index(repo.db)
        except Exception as exc:
            logger.warning("could not ensure signal dedup index: %s", exc)

    # ------------------------------------------------------------------
    # public surface
    # ------------------------------------------------------------------

    @property
    def stats(self) -> dict[str, Any]:
        with self._lock:
            return self._stats.as_dict()

    def process_signals(self, signals: list[ScannerSignal]) -> list[ExecutionDecision]:
        """Process a batch of scanner signals. Returns one decision per signal."""
        import logging as _l
        _l.getLogger("app.execution.bridge").info(
            "BRIDGE_PROCESS_SIGNALS received_count=%d", len(signals) if signals else 0
        )
        # Also write to a debug file we control
        with open("logs/bridge_debug.log", "a") as f:
            f.write(f"BRIDGE_PROCESS_SIGNALS received_count={len(signals) if signals else 0}\n")
            if signals:
                f.write(f"  first: symbol={signals[0].symbol} mode={signals[0].mode} side={signals[0].side}\n")
        decisions: list[ExecutionDecision] = []
        for sig in signals:
            try:
                decision = self._process_one(sig)
            except Exception as exc:
                logger.exception(
                    "[EXEC] unexpected failure for %s/%s: %s",
                    sig.strategy_name, sig.symbol, exc,
                )
                decision = ExecutionDecision(
                    signal_strategy_id=sig.strategy_id,
                    signal_symbol=sig.symbol,
                    signal_candle_epoch=0,
                    side=sig.side,
                    accepted=False,
                    rejection_stage="bridge_error",
                    risk_reason=str(exc),
                )
            decisions.append(decision)
        with self._lock:
            self._stats.last_decisions = decisions[-20:]
        return decisions

    # ------------------------------------------------------------------
    # internal
    # ------------------------------------------------------------------

    def _process_one(self, sig: ScannerSignal) -> ExecutionDecision:
        with self._lock:
            self._stats.signals_processed += 1

        # Mode gate — paper only here, testnet/live wired but not enabled
        if sig.mode == "live":
            with self._lock:
                self._stats.signals_wrong_mode += 1
            return ExecutionDecision(
                signal_strategy_id=sig.strategy_id,
                signal_symbol=sig.symbol,
                signal_candle_epoch=0,
                side=sig.side,
                accepted=False,
                rejection_stage="mode",
                risk_reason=f"signal mode {sig.mode!r} not permitted (bridge mode {self._mode!r})",
            )

        req = to_execution_request(sig)

        # DB-level dedup: a previous execution for the same candle is a no-op
        if self._is_already_executed(req):
            with self._lock:
                self._stats.signals_deduped_db += 1
            return ExecutionDecision(
                signal_strategy_id=req.strategy_id,
                signal_symbol=req.symbol,
                signal_candle_epoch=req.candle_close_epoch,
                side=req.side,
                accepted=False,
                rejection_stage="dedup",
                risk_reason="duplicate (strategy_id, symbol, candle_close_epoch) already executed",
            )

        # Mark the signal as "EXECUTING" so a concurrent worker won't re-pick it
        self._mark_signal_trading_status(req, "EXECUTING")

        # OrderManager.process_signal handles: HOLD skip, position-already-open skip,
        # risk.approve, ticker fetch, sizing, OrderRequest, paper place_order,
        # position return. Real components only — no parallel logic.
        result: OrderResult | None = self._orders.process_signal(
            req.signal,
            daily_pnl=Decimal("0"),
            open_positions=0,
            leverage=self._leverage,
            position_notional=self._paper_position_notional,
        )

        if result is None:
            # Either risk rejected, sizing failed, or position already open.
            # OrderManager doesn't surface the reason; we ask the risk manager
            # for the decision so the bridge can log a precise reason.
            decision = self._risk.approve(
                confidence=Decimal(str(req.signal.confidence)),
                daily_pnl=Decimal("0"),
                open_positions=0,
                leverage=self._leverage,
            )
            stage = "risk" if not decision.approved else "sizing"
            with self._lock:
                if stage == "risk":
                    self._stats.signals_risk_rejected += 1
                else:
                    self._stats.signals_sizing_rejected += 1
            self._mark_signal_trading_status(req, "REJECTED", reason=decision.reason)
            return ExecutionDecision(
                signal_strategy_id=req.strategy_id,
                signal_symbol=req.symbol,
                signal_candle_epoch=req.candle_close_epoch,
                side=req.side,
                accepted=False,
                rejection_stage=stage,
                risk_reason=decision.reason,
            )

        # Real order — persist it
        self._repo.save_order(result)
        self._repo.save_balance(self._orders.balance())

        position = self._orders.position(req.symbol)
        if position is not None:
            self._repo.save_position(position)
        # The position returned by OrderManager is in-memory. We need a
        # copy carrying strategy_id so /admin/positions can show owner.
        if position is not None:
            try:
                self._backfill_position_strategy_id(req.strategy_id, position)
            except Exception as exc:
                logger.debug("position strategy_id backfill skipped: %s", exc)

        # Place TP / SL conditional orders (only if the position exists)
        tp_order = sl_order = None
        if position is not None and position.quantity > 0:
            tp_order, sl_order = self._attach_tp_sl(req, position)

        # Mark the original signal as EXECUTED so duplicate cycles skip it
        self._mark_signal_trading_status(req, "EXECUTED")

        with self._lock:
            self._stats.signals_executed += 1

        return ExecutionDecision(
            signal_strategy_id=req.strategy_id,
            signal_symbol=req.symbol,
            signal_candle_epoch=req.candle_close_epoch,
            side=req.side,
            accepted=True,
            order_id=result.order_id,
            position_id=result.order_id,
            tp_order_id=tp_order.order_id if tp_order else None,
            sl_order_id=sl_order.order_id if sl_order else None,
            quantity=str(result.executed_quantity),
            entry_price=str(result.average_price) if result.average_price is not None else None,
        )

    # ------------------------------------------------------------------
    # dedup helpers
    # ------------------------------------------------------------------

    def _is_already_executed(self, req: ExecutionRequest) -> bool:
        """Return True if a prior signal for the same candle has already
        been EXECUTED, EXECUTING, or has a real order against it.
        """
        try:
            cols = [r[1] for r in self._repo.db.execute("PRAGMA table_info(signals)").fetchall()]
        except Exception:
            return False
        if "candle_close_epoch" not in cols:
            return False
        row = self._repo.db.execute(
            "SELECT trading_status, signal_status FROM signals "
            "WHERE strategy_id = ? AND symbol = ? AND candle_close_epoch = ? "
            "ORDER BY created_at DESC LIMIT 1",
            (req.strategy_id, req.symbol, req.candle_close_epoch),
        ).fetchone()
        if row is None:
            return False
        trading_status = row[0] or ""
        signal_status = row[1] or ""
        return trading_status in ("executed", "executing") or signal_status in ("executed",)

    def _mark_signal_trading_status(self, req: ExecutionRequest, status: str, reason: str | None = None) -> None:
        """Update the most recent matching signal row's trading_status.

        This is the bridge between the scanner's "CREATED/PENDING" row and
        the execution layer's verdict. Keeps signal audit trail intact.
        """
        try:
            cols = [r[1] for r in self._repo.db.execute("PRAGMA table_info(signals)").fetchall()]
        except Exception:
            return
        if "trading_status" not in cols:
            return
        params: list[Any] = [status.lower()]
        sets = ["trading_status = ?"]
        if "updated_at" in cols:
            sets.append("updated_at = ?")
            params.append(datetime.now(UTC).isoformat())
        if reason is not None and "rejection_reason" in cols:
            sets.append("rejection_reason = ?")
            params.append(reason)
        where = ["strategy_id = ?", "symbol = ?"]
        wp: list[Any] = [req.strategy_id, req.symbol]
        if "candle_close_epoch" in cols:
            where.append("candle_close_epoch = ?")
            wp.append(req.candle_close_epoch)
        params.extend(wp)
        sql = f"UPDATE signals SET {', '.join(sets)} WHERE {' AND '.join(where)}"
        try:
            self._repo.db.execute(sql, tuple(params))
        except Exception as exc:
            logger.debug("trading_status update skipped: %s", exc)

    # ------------------------------------------------------------------
    # TP/SL attachment
    # ------------------------------------------------------------------

    def _attach_tp_sl(
        self, req: ExecutionRequest, position: Position
    ) -> tuple[OrderResult | None, OrderResult | None]:
        """Place conditional TP and SL orders against the open position.

        Reuses the existing paper adapter's STOP_MARKET / TAKE_PROFIT_MARKET
        code path; update_market_price on the adapter will fire them when
        the live ticker crosses the threshold.
        """
        exchange = self._orders._exchange  # ExchangeAdapter (paper in this task)
        close_side = OrderSide.SELL if position.side.value == "BUY" else OrderSide.BUY
        tp_request = OrderRequest(
            symbol=req.symbol,
            side=close_side,
            order_type=OrderType.TAKE_PROFIT_MARKET,
            quantity=position.quantity,
            price=None,
            stop_price=Decimal(str(req.take_profit)),
        )
        sl_request = OrderRequest(
            symbol=req.symbol,
            side=close_side,
            order_type=OrderType.STOP_MARKET,
            quantity=position.quantity,
            price=None,
            stop_price=Decimal(str(req.stop_loss)),
        )
        tp_result = exchange.place_order(tp_request)
        sl_result = exchange.place_order(sl_request)
        self._repo.save_order(tp_result)
        self._repo.save_order(sl_result)
        return tp_result, sl_result

    # ------------------------------------------------------------------
    # position strategy_id attribution
    # ------------------------------------------------------------------

    def _backfill_position_strategy_id(self, strategy_id: str, position: Position) -> None:
        try:
            self._repo.db.execute(
                "UPDATE positions SET strategy_id = ? WHERE symbol = ?",
                (strategy_id, position.symbol),
            )
        except Exception:
            pass
