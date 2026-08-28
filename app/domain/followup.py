"""Follow-up domain entities."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
import uuid


class FollowupEventType(StrEnum):
    ENTRY_CONFIRMED = "entry_confirmed"
    TP1_HIT = "tp1_hit"
    TP2_HIT = "tp2_hit"
    SL_HIT = "sl_hit"
    STOP_MOVED = "stop_moved"
    POSITION_CLOSED = "position_closed"
    CANCELLED = "cancelled"
    NOTE = "note"


class FollowupExecutionStatus(StrEnum):
    PENDING = "pending"
    EXECUTED = "executed"
    SKIPPED = "skipped"
    FAILED = "failed"


@dataclass
class Followup:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    signal_id: str = ""
    event_type: FollowupEventType = FollowupEventType.ENTRY_CONFIRMED
    event_data: dict[str, Any] = field(default_factory=dict)
    publishing_status: dict[str, str] = field(default_factory=lambda: {"telegram": "pending", "square": "pending"})
    execution_status: FollowupExecutionStatus = FollowupExecutionStatus.PENDING
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "signal_id": self.signal_id,
            "event_type": self.event_type.value if isinstance(self.event_type, FollowupEventType) else self.event_type,
            "event_data": self.event_data,
            "publishing_status": self.publishing_status,
            "execution_status": self.execution_status.value if isinstance(self.execution_status, FollowupExecutionStatus) else self.execution_status,
            "created_at": self.created_at.isoformat() if hasattr(self.created_at, 'isoformat') else self.created_at,
        }
