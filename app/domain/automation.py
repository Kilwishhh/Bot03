"""Automation domain entities."""

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


class AutomationTrigger(StrEnum):
    SIGNAL_GENERATED = "signal_generated"
    TP1_HIT = "tp1_hit"
    TP2_HIT = "tp2_hit"
    SL_HIT = "sl_hit"
    STOP_MOVED = "stop_moved"
    POSITION_CLOSED = "position_closed"


class AutomationActionType(StrEnum):
    TELEGRAM_PUBLISH = "telegram_publish"
    SQUARE_PUBLISH = "square_publish"
    OPEN_TRADE = "open_trade"
    CLOSE_POSITION = "close_position"
    MOVE_STOP = "move_stop"
    NOTIFICATION = "notification"


@dataclass
class AutomationCondition:
    field: str        # e.g. "signal.confidence", "market", "side"
    op: str           # "gt", "lt", "eq", "gte", "lte", "in", "not_in"
    value: Any

    def to_dict(self) -> dict[str, Any]:
        return {"field": self.field, "op": self.op, "value": self.value}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "AutomationCondition":
        return cls(field=d["field"], op=d["op"], value=d["value"])


@dataclass
class AutomationAction:
    type: AutomationActionType
    params: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type.value if isinstance(self.type, AutomationActionType) else self.type,
            "params": self.params,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "AutomationAction":
        return cls(
            type=AutomationActionType(d.get("type", "")),
            params=d.get("params", {}),
        )


@dataclass
class AutomationRule:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str = ""
    strategy_id: str | None = None
    name: str = ""
    trigger: AutomationTrigger = AutomationTrigger.SIGNAL_GENERATED
    conditions: list[AutomationCondition] = field(default_factory=list)
    actions: list[AutomationAction] = field(default_factory=list)
    enabled: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "strategy_id": self.strategy_id,
            "name": self.name,
            "trigger": self.trigger.value if isinstance(self.trigger, AutomationTrigger) else self.trigger,
            "conditions": [c.to_dict() for c in self.conditions],
            "actions": [a.to_dict() for a in self.actions],
            "enabled": self.enabled,
            "created_at": self.created_at.isoformat() if hasattr(self.created_at, 'isoformat') else self.created_at,
            "updated_at": self.updated_at.isoformat() if hasattr(self.updated_at, 'isoformat') else self.updated_at,
        }


class AutomationEventStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"


@dataclass
class AutomationEvent:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    rule_id: str = ""
    signal_id: str | None = None
    followup_id: str | None = None
    status: AutomationEventStatus = AutomationEventStatus.PENDING
    result: dict[str, Any] | None = None
    attempts: int = 0
    dedup_key: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "rule_id": self.rule_id,
            "signal_id": self.signal_id,
            "followup_id": self.followup_id,
            "status": self.status.value if isinstance(self.status, AutomationEventStatus) else self.status,
            "result": self.result,
            "attempts": self.attempts,
            "dedup_key": self.dedup_key,
            "created_at": self.created_at.isoformat() if hasattr(self.created_at, 'isoformat') else self.created_at,
            "completed_at": self.completed_at.isoformat() if hasattr(self.completed_at, 'isoformat') else self.completed_at,
        }
