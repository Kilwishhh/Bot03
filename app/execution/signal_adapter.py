"""Adapter: convert a scanner ScannerSignal into a real execution Signal.

The scanner's ScannerSignal carries strategy_id, user_id, entry/tp/sl,
confidence, side, etc. OrderManager.process_signal() expects the
domain `app.signals.models.Signal`. This module is the smallest clean
bridge between the two types — no business logic, just a faithful
mapping. The immutable confidence/tp/sl snapshot is preserved.

Also produces an ExecutionRequest dataclass that bundles the signal
with its owner context (strategy_id, user_id) so the execution layer
can persist the resulting order/position with full provenance.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from app.signals.models import Signal, SignalSide

from ..strategy.scanner import ScannerSignal


@dataclass(frozen=True)
class ExecutionRequest:
    """Scanner signal wrapped with the context OrderManager needs."""

    signal: Signal
    strategy_id: str
    user_id: str
    candle_close_epoch: int           # dedup key epoch seconds
    take_profit: float
    stop_loss: float
    entry_price: float
    confidence_hits: int
    confidence_total: int
    mode: str                          # "paper" | "testnet" | "live"
    symbol: str
    side: str                          # "BUY" | "SELL"
    timeframe: str
    strategy_name: str


def to_execution_request(sig: ScannerSignal) -> ExecutionRequest:
    """Convert a ScannerSignal into an ExecutionRequest.

    Side mapping: ScannerSignal.side is already "BUY" or "SELL" (no HOLD
    ever reaches here — the scanner gates on matched=True which only
    happens for BUY/SELL direction).
    """
    side_enum = SignalSide.BUY if sig.side.upper() == "BUY" else SignalSide.SELL
    timestamp = datetime.fromisoformat(sig.candle_close_time.replace("Z", "+00:00"))
    signal = Signal(
        symbol=sig.symbol,
        side=side_enum,
        confidence=float(sig.confidence),
        timestamp=timestamp,
        reason=list(sig.reasons or []),
        strategy_name=sig.strategy_name,
        metadata={
            "strategy_id": sig.strategy_id,
            "user_id": sig.user_id,
            "entry_price": float(sig.entry),
            "take_profit": float(sig.take_profit),
            "stop_loss": float(sig.stop_loss),
            "timeframe": sig.timeframe,
            "mode": sig.mode,
            "candle_close_time": sig.candle_close_time,
            "candle_age_seconds": sig.candle_age_seconds,
            "confidence_hits": sig.confidence_hits,
            "confidence_total": sig.confidence_total,
            "indicators": sig.indicators,
        },
    )
    candle_epoch = int(timestamp.timestamp())

    return ExecutionRequest(
        signal=signal,
        strategy_id=sig.strategy_id,
        user_id=sig.user_id,
        candle_close_epoch=candle_epoch,
        take_profit=float(sig.take_profit),
        stop_loss=float(sig.stop_loss),
        entry_price=float(sig.entry),
        confidence_hits=int(sig.confidence_hits),
        confidence_total=int(sig.confidence_total),
        mode=sig.mode,
        symbol=sig.symbol,
        side=sig.side.upper(),
        timeframe=sig.timeframe,
        strategy_name=sig.strategy_name,
    )


def make_entry_order_request(req: ExecutionRequest, quantity: Decimal, price: Decimal):
    """Build a domain OrderRequest for the entry leg.

    We import lazily so importing this module never pulls in the rest of
    the execution stack at import time.
    """
    from app.exchange.models import OrderRequest, OrderSide, OrderType

    side = OrderSide.BUY if req.side == "BUY" else OrderSide.SELL
    return OrderRequest(
        symbol=req.symbol,
        side=side,
        order_type=OrderType.MARKET,
        quantity=quantity,
        price=price,
    )
