"""Strategy domain entities."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


class LifecycleState(StrEnum):
    DRAFT = "draft"
    BACKTEST = "backtest"
    PAPER = "paper"
    TESTNET = "testnet"
    LIVE_ELIGIBLE = "live_eligible"
    LIVE = "live"
    PAUSED = "paused"
    STOPPED = "stopped"


class ExecutionMode(StrEnum):
    PAPER = "paper"
    TESTNET = "testnet"
    LIVE = "live"


class ExecutionVenue(StrEnum):
    BINANCE = "binance"
    HYPERLIQUID = "hyperliquid"
    WALLETCONNECT = "walletconnect"


class Timeframe(StrEnum):
    M1 = "1m"
    M5 = "5m"
    M15 = "15m"
    H1 = "1h"
    H4 = "4h"
    D1 = "1d"


# Valid forward transitions (from_state → set of to_state)
LIFECYCLE_GRAPH: dict[LifecycleState, set[LifecycleState]] = {
    LifecycleState.DRAFT:          {LifecycleState.BACKTEST, LifecycleState.PAUSED},
    LifecycleState.BACKTEST:       {LifecycleState.PAPER, LifecycleState.PAUSED, LifecycleState.STOPPED},
    LifecycleState.PAPER:          {LifecycleState.TESTNET, LifecycleState.PAUSED, LifecycleState.STOPPED},
    LifecycleState.TESTNET:        {LifecycleState.LIVE_ELIGIBLE, LifecycleState.PAUSED, LifecycleState.STOPPED},
    LifecycleState.LIVE_ELIGIBLE:  {LifecycleState.LIVE, LifecycleState.PAUSED, LifecycleState.STOPPED},
    LifecycleState.LIVE:           {LifecycleState.PAUSED, LifecycleState.STOPPED},
    LifecycleState.PAUSED:        {LifecycleState.DRAFT, LifecycleState.BACKTEST, LifecycleState.PAPER,
                                   LifecycleState.TESTNET, LifecycleState.LIVE_ELIGIBLE,
                                   LifecycleState.STOPPED},
    LifecycleState.STOPPED:        {LifecycleState.DRAFT},  # restart from scratch
}


def is_valid_transition(from_state: LifecycleState, to_state: LifecycleState) -> bool:
    return to_state in LIFECYCLE_GRAPH.get(from_state, set())


@dataclass
class EntryConfig:
    indicators: list[dict[str, Any]] = field(default_factory=list)
    conditions: list[dict[str, Any]] = field(default_factory=list)
    template: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"indicators": self.indicators, "conditions": self.conditions, "template": self.template}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "EntryConfig":
        return cls(indicators=d.get("indicators", []), conditions=d.get("conditions", []),
                   template=d.get("template"))


@dataclass
class ExitConfig:
    tp1_pct: float = 0.01
    tp2_pct: float = 0.02
    stop_loss_pct: float = 0.005
    trailing_stop: bool = False
    trailing_pct: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "tp1_pct": self.tp1_pct, "tp2_pct": self.tp2_pct,
            "stop_loss_pct": self.stop_loss_pct,
            "trailing_stop": self.trailing_stop, "trailing_pct": self.trailing_pct,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ExitConfig":
        return cls(
            tp1_pct=float(d.get("tp1_pct", 0.01)),
            tp2_pct=float(d.get("tp2_pct", 0.02)),
            stop_loss_pct=float(d.get("stop_loss_pct", 0.005)),
            trailing_stop=bool(d.get("trailing_stop", False)),
            trailing_pct=float(d.get("trailing_pct", 0.0)),
        )


@dataclass
class RiskConfig:
    max_per_trade: float = 0.02      # fraction of balance per trade
    max_daily_loss: float = 0.05     # fraction of balance
    max_open_positions: int = 3
    max_leverage: int = 10
    max_exposure: float = 0.5        # fraction of balance across all positions

    def to_dict(self) -> dict[str, Any]:
        return {
            "max_per_trade": self.max_per_trade,
            "max_daily_loss": self.max_daily_loss,
            "max_open_positions": self.max_open_positions,
            "max_leverage": self.max_leverage,
            "max_exposure": self.max_exposure,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "RiskConfig":
        return cls(
            max_per_trade=float(d.get("max_per_trade", 0.02)),
            max_daily_loss=float(d.get("max_daily_loss", 0.05)),
            max_open_positions=int(d.get("max_open_positions", 3)),
            max_leverage=int(d.get("max_leverage", 10)),
            max_exposure=float(d.get("max_exposure", 0.5)),
        )


@dataclass
class Strategy:
    id: str
    user_id: str
    name: str
    description: str | None = None
    version: int = 1
    lifecycle_state: LifecycleState = LifecycleState.DRAFT
    execution_mode: ExecutionMode = ExecutionMode.PAPER
    execution_venue: ExecutionVenue = ExecutionVenue.BINANCE
    market: str = "BTCUSDT"
    timeframe: Timeframe = Timeframe.M15
    entry_config: EntryConfig = field(default_factory=EntryConfig)
    exit_config: ExitConfig = field(default_factory=ExitConfig)
    risk_config: RiskConfig = field(default_factory=RiskConfig)
    template_name: str | None = None
    template_params: dict[str, Any] = field(default_factory=dict)
    automation_id: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def can_transition_to(self, new_state: LifecycleState) -> bool:
        return is_valid_transition(self.lifecycle_state, new_state)

    def is_live(self) -> bool:
        return self.lifecycle_state == LifecycleState.LIVE

    def is_active(self) -> bool:
        return self.lifecycle_state not in (LifecycleState.STOPPED, LifecycleState.PAUSED)

    def is_live_eligible(self) -> bool:
        return self.lifecycle_state == LifecycleState.LIVE_ELIGIBLE


@dataclass
class LifecycleEvent:
    id: int | None = None
    strategy_id: str = ""
    from_state: LifecycleState | None = None
    to_state: LifecycleState = LifecycleState.DRAFT
    actor_user_id: str | None = None
    actor_role: str = "system"
    reason: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class StrategyVersion:
    id: str
    strategy_id: str
    version: int
    config_snapshot: dict[str, Any]
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class Backtest:
    id: str
    strategy_id: str
    user_id: str
    status: str = "queued"  # queued | running | completed | failed
    result_summary: dict[str, Any] | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error_message: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
