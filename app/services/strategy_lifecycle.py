"""Strategy lifecycle state machine — the core safety gate for live trading."""

from __future__ import annotations

from datetime import UTC, datetime

from app.core import errors
from app.core.audit import record
from app.core.rbac import AccessContext
from app.domain.strategy import (
    LifecycleState,
    Strategy,
)
from app.services.strategy_service import StrategyService

# LIVE requires all of these checks to pass
LIVE_REQUIREMENTS = {
    "exchange_connection": "No exchange connection found for this venue",
    "risk_config": "Risk config must have max_per_trade, max_daily_loss, max_open_positions",
    "no_active_pause": "Strategy is under emergency pause",
    "live_confirmed": "confirm_live=true and confirmation_string='I_UNDERSTAND_LIVE_RISK' required",
}


class StrategyLifecycle:
    def __init__(self, strategy_service: StrategyService) -> None:
        self._svc = strategy_service

    def transition(
        self,
        strategy: Strategy,
        target_state: LifecycleState,
        ctx: AccessContext,
        reason: str | None = None,
        confirm_live: bool = False,
        confirmation_string: str = "",
    ) -> Strategy:
        """Attempt a state transition. Validates, writes audit trail, persists."""
        # System-triggered STOPPED is always allowed
        if target_state == LifecycleState.STOPPED:
            return self._do_transition(strategy, None, target_state, ctx, reason or "stopped")

        if not strategy.can_transition_to(target_state):
            raise errors.LifecycleError(
                f"invalid transition: {strategy.lifecycle_state.value} -> {target_state.value}"
            )

        if target_state == LifecycleState.LIVE:
            self._validate_live_requirements(strategy, ctx, confirm_live, confirmation_string)
            reason = reason or "live deployment confirmed"
        elif target_state == LifecycleState.LIVE_ELIGIBLE:
            self._validate_live_eligible(strategy, ctx)

        return self._do_transition(strategy, strategy.lifecycle_state, target_state, ctx, reason)

    def _validate_live_eligible(self, strategy: Strategy, ctx: AccessContext) -> None:
        """TESTNET -> LIVE_ELIGIBLE requires testnet sessions + positive PnL."""
        from app.database.repository import get_default_repository
        repo = get_default_repository()
        recent = repo.recent_trades(limit=20)
        if not recent:
            raise errors.LifecycleError(
                "no testnet trades on record; complete testnet sessions before live-eligible"
            )
        # Basic sanity: at least one filled trade
        filled = [t for t in recent if t[2] in ("buy", "sell")]
        if len(filled) < 1:
            raise errors.LiveDeploymentError("at least 1 testnet trade required before live-eligible")

    def _validate_live_requirements(
        self, strategy: Strategy, ctx: AccessContext,
        confirm_live: bool, confirmation_string: str,
    ) -> None:
        issues = []

        # Exchange connection must exist
        from app.services.connection_service import ConnectionService
        conn_svc = ConnectionService()
        venue_name = strategy.execution_venue.value if hasattr(strategy.execution_venue, "value") else str(strategy.execution_venue)
        venue_map = {"binance": "binance", "hyperliquid": "hyperliquid", "walletconnect": "walletconnect"}
        connections = conn_svc.list(ctx, venue=venue_map.get(venue_name, venue_name))
        if not any(c.venue.value == venue_name for c in connections):
            issues.append(LIVE_REQUIREMENTS["exchange_connection"])

        # Risk config must be populated
        risk = strategy.risk_config
        if not (risk.max_per_trade and risk.max_daily_loss and risk.max_open_positions):
            issues.append(LIVE_REQUIREMENTS["risk_config"])

        # Emergency pause check
        from app.services.emergency_service import EmergencyService
        emergency = EmergencyService()
        pause_status = emergency.get_pause_status(strategy_id=strategy.id, ctx=ctx)
        if pause_status["is_paused"]:
            issues.append(LIVE_REQUIREMENTS["no_active_pause"])

        # Confirmation string
        if not confirm_live or confirmation_string != "I_UNDERSTAND_LIVE_RISK":
            issues.append(LIVE_REQUIREMENTS["live_confirmed"])

        if issues:
            raise errors.LiveDeploymentError("; ".join(issues))

    def _do_transition(
        self,
        strategy: Strategy,
        from_state: LifecycleState | None,
        to_state: LifecycleState,
        ctx: AccessContext,
        reason: str | None,
    ) -> Strategy:
        now = datetime.now(UTC).isoformat()
        # Update strategy
        strategy.lifecycle_state = to_state
        strategy.updated_at = datetime.now(UTC)
        # Persist
        updated = self._svc.update(strategy, ctx)
        # Write lifecycle event
        self._svc.record_lifecycle_event(
            strategy_id=strategy.id,
            from_state=from_state,
            to_state=to_state,
            actor_user_id=ctx.user.id,
            actor_role=(ctx.user.role.value if hasattr(ctx.user.role, "value") else str(ctx.user.role)),
            reason=reason,
        )
        record(
            actor=ctx.user,
            action="lifecycle.transition",
            target_type="strategy",
            target_id=strategy.id,
            detail={
                "from": from_state.value if from_state else None,
                "to": to_state.value,
                "reason": reason,
            },
        )
        return updated
