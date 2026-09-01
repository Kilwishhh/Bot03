"""Signal service: create, update status, filter signals."""

from __future__ import annotations

import sqlite3
import threading
from datetime import UTC, datetime
from typing import Any

from app.core import errors
from app.core.audit import record
from app.core.rbac import AccessContext
from app.domain.signal import (
    PublishStatus,
    Signal,
    SignalStatus,
    TradingStatus,
)
from app.signals.models import Signal as _LegacySignal
from app.config import Settings


def _enum_or(enum_cls, value: str | None, default):
    if value is None:
        return default
    try:
        return enum_cls(value)
    except ValueError:
        return default


class SignalService:
    def __init__(self, db_path: str | None = None) -> None:
        self._db_path = db_path or Settings().database_path
        self._lock = threading.RLock()

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(self._db_path, check_same_thread=False, isolation_level=None)

    def create(self, signal: Signal | _LegacySignal, ctx: AccessContext) -> Signal:
        """Persist a new signal (from strategy engine)."""
        if isinstance(signal, _LegacySignal):
            s = Signal.from_legacy(signal, user_id=ctx.user.id)
        else:
            s = signal
            if not s.user_id or s.user_id == "system":
                s.user_id = ctx.user.id

        conn = self._conn()
        try:
            now = datetime.now(UTC).isoformat()
            with self._lock:
                conn.execute(
                    "INSERT INTO signals (id, user_id, strategy_id, symbol, side, confidence, "
                    "entry_price, tp1, tp2, stop_loss, mode, signal_status, trading_status, "
                    "telegram_status, square_status, timestamp, reason, strategy, "
                    "created_at, updated_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        s.id, s.user_id, s.strategy_id, s.symbol,
                        (s.side.value if hasattr(s.side, "value") else s.side),
                        s.confidence, s.entry_price, s.tp1, s.tp2, s.stop_loss,
                        s.mode,
                        (s.signal_status.value if hasattr(s.signal_status, "value") else s.signal_status),
                        (s.trading_status.value if hasattr(s.trading_status, "value") else s.trading_status),
                        (s.telegram_status.value if hasattr(s.telegram_status, "value") else s.telegram_status),
                        (s.square_status.value if hasattr(s.square_status, "value") else s.square_status),
                        (s.timestamp.isoformat() if hasattr(s.timestamp, "isoformat") else s.timestamp),
                        "; ".join(s.reason) if s.reason else "",
                        s.strategy_name, now, now,
                    ),
                )
            record(actor=ctx.user, action="signal.create",
                   target_type="signal", target_id=s.id,
                   detail={"symbol": s.symbol, "side": str(s.side), "mode": s.mode})
            return s
        finally:
            conn.close()

    def get(self, signal_id: str, ctx: AccessContext) -> Signal:
        conn = self._conn()
        try:
            row = conn.execute("SELECT * FROM signals WHERE id = ?", (signal_id,)).fetchone()
            if not row:
                raise errors.NotFoundError("signal not found")
            s = self._row_to_signal(row)
            if s.user_id != ctx.user.id and not ctx.is_admin():
                raise errors.NotFoundError("signal not found")
            return s
        finally:
            conn.close()

    def list(self, ctx: AccessContext, filter_status: str | None = None,
             limit: int = 50, offset: int = 0) -> list[Signal]:
        conn = self._conn()
        try:
            q = "SELECT * FROM signals WHERE user_id = ?"
            params: list[Any] = [ctx.user.id]
            if filter_status:
                q += " AND signal_status = ?"
                params.append(filter_status)
            q += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])
            return [self._row_to_signal(r) for r in conn.execute(q, params).fetchall()]
        finally:
            conn.close()

    def update_status(self, signal_id: str, signal_status: SignalStatus,
                     ctx: AccessContext) -> Signal:
        s = self.get(signal_id, ctx)
        conn = self._conn()
        try:
            with self._lock:
                conn.execute(
                    "UPDATE signals SET signal_status = ?, updated_at = ? WHERE id = ?",
                    (signal_status.value, datetime.now(UTC).isoformat(), signal_id),
                )
            record(actor=ctx.user, action="signal.status_update",
                   target_type="signal", target_id=signal_id,
                   detail={"signal_status": signal_status.value})
            return self.get(signal_id, ctx)
        finally:
            conn.close()

    def update_trading_status(self, signal_id: str, trading_status: TradingStatus,
                             ctx: AccessContext) -> Signal:
        conn = self._conn()
        try:
            with self._lock:
                conn.execute(
                    "UPDATE signals SET trading_status = ?, updated_at = ? WHERE id = ?",
                    (trading_status.value, datetime.now(UTC).isoformat(), signal_id),
                )
            return self.get(signal_id, ctx)
        finally:
            conn.close()

    def update_publishing_status(self, signal_id: str, channel: str,
                                status: PublishStatus, ctx: AccessContext) -> None:
        col = "telegram_status" if channel == "telegram" else "square_status"
        conn = self._conn()
        try:
            with self._lock:
                conn.execute(
                    f"UPDATE signals SET {col} = ?, updated_at = ? WHERE id = ?",
                    (status.value, datetime.now(UTC).isoformat(), signal_id),
                )
        finally:
            conn.close()

    def _row_to_signal(self, row: tuple) -> Signal:
        cols = self._signal_columns()
        d = dict(zip(cols, row, strict=False))
        return Signal(
            id=d.get("id") or "",
            user_id=d.get("user_id") or "system",
            strategy_id=d.get("strategy_id"),
            symbol=d.get("symbol") or "",
            side=d.get("side") or "HOLD",
            confidence=float(d.get("confidence") or 0),
            entry_price=float(d["entry_price"]) if d.get("entry_price") else None,
            tp1=float(d["tp1"]) if d.get("tp1") else None,
            tp2=float(d["tp2"]) if d.get("tp2") else None,
            stop_loss=float(d["stop_loss"]) if d.get("stop_loss") else None,
            mode=d.get("mode") or "paper",
            signal_status=_enum_or(SignalStatus, d.get("signal_status"), SignalStatus.ACTIVE),
            trading_status=_enum_or(TradingStatus, d.get("trading_status"), TradingStatus.PENDING),
            telegram_status=_enum_or(PublishStatus, d.get("telegram_status"), PublishStatus.PENDING),
            square_status=_enum_or(PublishStatus, d.get("square_status"), PublishStatus.PENDING),
            timestamp=datetime.fromisoformat(d["timestamp"]) if d.get("timestamp") else datetime.now(UTC),
            reason=[r.strip() for r in d["reason"].split(";")] if d.get("reason") else [],
            strategy_name=d.get("strategy") or "unknown",
            created_at=datetime.fromisoformat(d["created_at"]) if d.get("created_at") else datetime.now(UTC),
            updated_at=datetime.fromisoformat(d["updated_at"]) if d.get("updated_at") else datetime.now(UTC),
        )

    def _signal_columns(self) -> list[str]:
        conn = self._conn()
        try:
            return [r[1] for r in conn.execute("PRAGMA table_info(signals)").fetchall()]
        finally:
            conn.close()
