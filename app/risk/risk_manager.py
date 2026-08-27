"""Strategy-independent trade admission controls."""

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class RiskDecision:
    approved: bool
    reason: str


class RiskManager:
    def __init__(self, max_daily_loss: Decimal, max_open_positions: int, min_confidence: Decimal, max_leverage: int, max_exposure: Decimal | None = None, max_consecutive_losses: int | None = None) -> None:
        self.max_daily_loss = max_daily_loss
        self.max_open_positions = max_open_positions
        self.min_confidence = min_confidence
        self.max_leverage = max_leverage
        self.max_exposure = max_exposure
        self.max_consecutive_losses = max_consecutive_losses
        self.consecutive_losses = 0
        self.emergency_stop = False

    def activate_emergency_stop(self) -> None:
        self.emergency_stop = True

    def reset_emergency_stop(self) -> None:
        self.emergency_stop = False

    def approve(self, confidence: Decimal, daily_pnl: Decimal, open_positions: int, leverage: int, current_exposure: Decimal = Decimal("0")) -> RiskDecision:
        if self.emergency_stop:
            return RiskDecision(False, "emergency stop is active")
        if confidence < self.min_confidence:
            return RiskDecision(False, "signal confidence is below minimum")
        if daily_pnl <= -abs(self.max_daily_loss):
            return RiskDecision(False, "daily loss limit reached")
        if open_positions >= self.max_open_positions:
            return RiskDecision(False, "maximum open positions reached")
        if leverage > self.max_leverage:
            return RiskDecision(False, "leverage exceeds configured maximum")
        if self.max_exposure is not None and current_exposure >= self.max_exposure:
            return RiskDecision(False, "maximum exposure reached")
        if self.max_consecutive_losses is not None and self.consecutive_losses >= self.max_consecutive_losses:
            return RiskDecision(False, "maximum consecutive losses reached")
        return RiskDecision(True, "approved")

    def record_trade(self, pnl: Decimal) -> None:
        self.consecutive_losses = self.consecutive_losses + 1 if pnl < 0 else 0
