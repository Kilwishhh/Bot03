"""Signal domain entities — extends the existing Signal model."""

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from app.signals.models import Signal as _LegacySignal
from app.signals.models import SignalSide


class SignalStatus(StrEnum):
    CREATED = "created"
    PENDING = "pending"
    ACTIVE = "active"
    ENTRY_CONFIRMED = "entry_confirmed"
    TP1_HIT = "tp1_hit"
    TP2_HIT = "tp2_hit"
    SL_HIT = "sl_hit"
    CLOSED = "closed"
    CANCELLED = "cancelled"


class TradingStatus(StrEnum):
    PENDING = "pending"
    EXECUTED = "executed"
    PLACED = "placed"
    REJECTED = "rejected"
    FILLED = "filled"
    CLOSED = "closed"


class PublishStatus(StrEnum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    RATE_LIMITED = "rate_limited"
    DUPLICATE = "duplicate"


@dataclass
class Signal:
    # New fields
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str = "system"
    strategy_id: str | None = None
    entry_price: float | None = None
    tp1: float | None = None
    tp2: float | None = None
    stop_loss: float | None = None
    mode: str = "paper"
    signal_status: SignalStatus = SignalStatus.ACTIVE
    trading_status: TradingStatus = TradingStatus.PENDING
    telegram_status: PublishStatus = PublishStatus.PENDING
    square_status: PublishStatus = PublishStatus.PENDING
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    # Legacy Signal fields
    symbol: str = ""
    side: SignalSide = SignalSide.HOLD
    confidence: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    reason: list[str] = field(default_factory=list)
    strategy_name: str = "unknown"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "strategy_id": self.strategy_id,
            "symbol": self.symbol,
            "side": self.side.value if isinstance(self.side, SignalSide) else self.side,
            "confidence": self.confidence,
            "entry_price": self.entry_price,
            "tp1": self.tp1,
            "tp2": self.tp2,
            "stop_loss": self.stop_loss,
            "mode": self.mode,
            "signal_status": self.signal_status.value if isinstance(self.signal_status, SignalStatus) else self.signal_status,
            "trading_status": self.trading_status.value if isinstance(self.trading_status, TradingStatus) else self.trading_status,
            "telegram_status": self.telegram_status.value if isinstance(self.telegram_status, PublishStatus) else self.telegram_status,
            "square_status": self.square_status.value if isinstance(self.square_status, PublishStatus) else self.square_status,
            "timestamp": self.timestamp.isoformat() if hasattr(self.timestamp, 'isoformat') else self.timestamp,
            "created_at": self.created_at.isoformat() if hasattr(self.created_at, 'isoformat') else self.created_at,
            "updated_at": self.updated_at.isoformat() if hasattr(self.updated_at, 'isoformat') else self.updated_at,
            "reason": self.reason,
            "strategy_name": self.strategy_name,
            "metadata": self.metadata,
        }

    @classmethod
    def from_legacy(cls, s: _LegacySignal, user_id: str = "system",
                     strategy_id: str | None = None) -> "Signal":
        return cls(
            symbol=s.symbol,
            side=s.side,
            confidence=s.confidence,
            timestamp=s.timestamp,
            reason=s.reason,
            strategy_name=s.strategy_name,
            metadata=s.metadata,
            user_id=user_id,
            strategy_id=strategy_id,
        )
