"""Connection + publishing domain entities."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


class ConnectionVenue(StrEnum):
    BINANCE = "binance"
    HYPERLIQUID = "hyperliquid"
    WALLETCONNECT = "walletconnect"


class ConnectionStatus(StrEnum):
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"


@dataclass
class ExchangeConnection:
    id: str = ""
    user_id: str = ""
    venue: ConnectionVenue = ConnectionVenue.BINANCE
    label: str | None = None
    api_key_enc: bytes = b""
    api_secret_enc: bytes | None = None
    wallet_address: str | None = None
    permissions: dict[str, bool] = field(default_factory=lambda: {"read": True, "trade": False, "withdraw": False})
    status: ConnectionStatus = ConnectionStatus.DISCONNECTED
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "venue": self.venue.value if isinstance(self.venue, ConnectionVenue) else self.venue,
            "label": self.label,
            "status": self.status.value if isinstance(self.status, ConnectionStatus) else self.status,
            "wallet_address": self.wallet_address,
            "permissions": self.permissions,
            "created_at": self.created_at.isoformat() if hasattr(self.created_at, 'isoformat') else self.created_at,
            "updated_at": self.updated_at.isoformat() if hasattr(self.updated_at, 'isoformat') else self.updated_at,
        }


class SquareLimitBehavior(StrEnum):
    STOP_SQUARE = "stop_square"
    TELEGRAM_ONLY = "telegram_only"
    QUEUE = "queue"


@dataclass
class PublishingConfig:
    user_id: str = ""
    telegram_token_enc: bytes | None = None
    telegram_chat_id: str | None = None
    telegram_enabled: bool = False
    square_api_key_enc: bytes | None = None
    square_endpoint: str | None = None
    square_daily_limit: int = 95
    square_limit_behavior: SquareLimitBehavior = SquareLimitBehavior.QUEUE
    square_enabled: bool = False
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class PublicationStatus(StrEnum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    RATE_LIMITED = "rate_limited"
    DUPLICATE = "duplicate"


class PublicationChannel(StrEnum):
    TELEGRAM = "telegram"
    BINANCE_SQUARE = "binance_square"


@dataclass
class Publication:
    id: str = ""
    user_id: str = ""
    signal_id: str | None = None
    channel: PublicationChannel = PublicationChannel.BINANCE_SQUARE
    status: PublicationStatus = PublicationStatus.PENDING
    posted_at: datetime | None = None
    error_message: str | None = None
    dedup_key: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class EmergencyScope(StrEnum):
    STRATEGY = "strategy"
    USER = "user"
    INTEGRATION = "integration"
    PLATFORM = "platform"


@dataclass
class EmergencyPause:
    id: str = ""
    scope: EmergencyScope = EmergencyScope.PLATFORM
    scope_target: str | None = None
    actor_user_id: str = ""
    actor_role: str = "system"
    reason: str = ""
    close_positions: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    expires_at: datetime | None = None
    resumed_at: datetime | None = None


@dataclass
class AuditEntry:
    id: int | None = None
    actor_user_id: str | None = None
    actor_role: str = "system"
    action: str = ""
    target_type: str | None = None
    target_id: str | None = None
    detail: dict[str, Any] | None = None
    result: str = "ok"  # ok | rejected | error
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
