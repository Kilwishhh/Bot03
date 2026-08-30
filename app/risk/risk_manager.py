"""Strategy-independent trade admission controls."""

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class RiskDecision:
    approved: bool
    reason: str


class RiskManager:
    def __init__(self, max_daily_loss: Decimal, max_open_positions: int, min_confidence: Decimal, max_leverage: int, max_exposure: Decimal | None = None, max_consecutive_losses: int | None = None, max_drawdown_pct: Decimal | None = None) -> None:
        self.max_daily_loss = max_daily_loss
        self.max_open_positions = max_open_positions
        self.min_confidence = min_confidence
        self.max_leverage = max_leverage
        self.max_exposure = max_exposure
        self.max_consecutive_losses = max_consecutive_losses
        self.max_drawdown_pct = max_drawdown_pct
        self.consecutive_losses = 0
        self.peak_equity: Decimal | None = None
        self.emergency_stop = False
        self.emergency_stop_reason: str | None = None

    def activate_emergency_stop(self, reason: str = "manual") -> None:
        self.emergency_stop = True
        self.emergency_stop_reason = reason

    def reset_emergency_stop(self) -> None:
        self.emergency_stop = False
        self.emergency_stop_reason = None
        self.peak_equity = None
        self.consecutive_losses = 0

    def update_equity(self, current_equity: Decimal) -> None:
        """Track peak equity for drawdown calculations."""
        if self.peak_equity is None or current_equity > self.peak_equity:
            self.peak_equity = current_equity

    def current_drawdown(self, current_equity: Decimal) -> Decimal:
        """Return current drawdown as positive Decimal (e.g. 0.05 = 5%)."""
        if self.peak_equity is None or self.peak_equity <= 0:
            return Decimal("0")
        return max(Decimal("0"), (self.peak_equity - current_equity) / self.peak_equity)

    def approve(self, confidence: Decimal, daily_pnl: Decimal, open_positions: int, leverage: int, current_exposure: Decimal = Decimal("0"), current_equity: Decimal | None = None) -> RiskDecision:
        if self.emergency_stop:
            return RiskDecision(False, f"emergency stop active: {self.emergency_stop_reason or 'manual'}")
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
        if (self.max_drawdown_pct is not None and current_equity is not None
                and self.peak_equity is not None and self.peak_equity > 0):
            drawdown = (self.peak_equity - current_equity) / self.peak_equity
            if drawdown >= self.max_drawdown_pct:
                self.activate_emergency_stop(f"max drawdown {drawdown*100:.1f}% reached")
                return RiskDecision(False, f"max drawdown {drawdown*100:.1f}% reached — emergency stop triggered")
        return RiskDecision(True, "approved")

    def record_trade(self, pnl: Decimal) -> None:
        self.consecutive_losses = self.consecutive_losses + 1 if pnl < 0 else 0
        if pnl < 0 and self.max_consecutive_losses is not None and self.consecutive_losses >= self.max_consecutive_losses:
            self.activate_emergency_stop(f"{self.consecutive_losses} consecutive losses")

    def snapshot(self) -> dict:
        """Return current risk state for telemetry / admin view."""
        return {
            "emergency_stop": self.emergency_stop,
            "emergency_stop_reason": self.emergency_stop_reason,
            "consecutive_losses": self.consecutive_losses,
            "peak_equity": str(self.peak_equity) if self.peak_equity is not None else None,
            "max_daily_loss": str(self.max_daily_loss),
            "max_open_positions": self.max_open_positions,
            "max_leverage": self.max_leverage,
            "max_drawdown_pct": str(self.max_drawdown_pct) if self.max_drawdown_pct is not None else None,
        }
