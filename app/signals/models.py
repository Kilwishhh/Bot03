"""Standardized strategy output."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any


class SignalSide(StrEnum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


@dataclass(frozen=True)
class Signal:
    symbol: str
    side: SignalSide
    confidence: float
    timestamp: datetime
    reason: list[str] = field(default_factory=list)
    strategy_name: str = "unknown"
    metadata: dict[str, Any] = field(default_factory=dict)
