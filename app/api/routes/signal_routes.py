"""Signal routes: /signals/* — list (public legacy), get/create (auth)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies import get_access_context
from app.core.errors import NotFoundError
from app.core.rbac import AccessContext
from app.domain.signal import SignalStatus

router = APIRouter(prefix="/signals", tags=["signals"])


def _serialize(s) -> dict:
    return s.to_dict()


# GET /signals is handled by the public legacy endpoint in server.py
# so the mobile app continues to work without auth.
#
# Auth-gated endpoints below:


@router.post("")
def create_signal(
    payload: dict,
    ctx: AccessContext = Depends(get_access_context),
):
    from app.domain.signal import Signal
    from app.services.signal_service import SignalService
    from app.signals.models import SignalSide
    svc = SignalService()
    try:
        side = SignalSide(payload.get("side", "HOLD"))
    except ValueError:
        raise HTTPException(status_code=400, detail="side must be BUY, SELL, or HOLD")
    sig = Signal(
        symbol=payload.get("symbol", ""),
        side=side,
        confidence=float(payload.get("confidence", 0)),
        strategy_name=payload.get("strategy_name", "manual"),
        user_id=ctx.user.id,
        strategy_id=payload.get("strategy_id"),
        entry_price=payload.get("entry_price"),
        tp1=payload.get("tp1"),
        tp2=payload.get("tp2"),
        stop_loss=payload.get("stop_loss"),
        mode=payload.get("mode", "paper"),
        reason=payload.get("reason", []),
    )
    saved = svc.create(sig, ctx)
    try:
        from app.services.automation_engine import AutomationEngine
        AutomationEngine().on_signal_generated(saved.id, ctx)
    except Exception:
        pass
    return _serialize(saved)


@router.get("/{signal_id}")
def get_signal(
    signal_id: str,
    ctx: AccessContext = Depends(get_access_context),
):
    from app.config import Settings
    from app.database import TradingRepository
    from app.services.signal_service import SignalService
    svc = SignalService()
    try:
        sig = svc.get(signal_id, ctx)
        result = sig.to_dict()
        # Enrich with trade data if executed
        repo = TradingRepository(Settings().database_path)
        ep = result.get("entry_price")
        trade_rows = []
        if ep:
            trade_rows = repo._connection.execute(
                "SELECT trade_id, side, quantity, entry_price, exit_price, realized_pnl, fees, entry_time, exit_time "
                "FROM trades WHERE symbol=? AND CAST(entry_price AS REAL)=CAST(? AS REAL) "
                "ORDER BY entry_time DESC LIMIT 1",
                (result.get("symbol"), ep)).fetchall()
        if trade_rows:
            t = trade_rows[0]
            result["trade"] = {
                "trade_id": t[0], "side": t[1], "quantity": t[2],
                "entry_price": t[3], "exit_price": t[4],
                "realized_pnl": t[5], "fees": t[6],
                "entry_time": t[7], "exit_time": t[8],
            }
            tp = result.get("tp1")
            sl = result.get("stop_loss")
            if ep and tp and sl:
                try:
                    ep_f = float(ep); tp_f = float(tp); sl_f = float(sl)
                    risk = abs(ep_f - sl_f)
                    reward = abs(tp_f - ep_f)
                    result["risk_reward"] = round(reward / risk, 2) if risk else None
                except (ValueError, TypeError, ZeroDivisionError):
                    pass
        repo.close()
        return result
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=e.message)


@router.patch("/{signal_id}/status")
def update_signal_status(
    signal_id: str,
    payload: dict,
    ctx: AccessContext = Depends(get_access_context),
):
    from app.services.signal_service import SignalService
    svc = SignalService()
    try:
        status = SignalStatus(payload["signal_status"])
        return _serialize(svc.update_status(signal_id, status, ctx))
    except (ValueError, KeyError):
        raise HTTPException(status_code=400, detail="invalid signal_status")
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=e.message)


@router.get("/{signal_id}/followups")
def list_signal_followups(
    signal_id: str,
    ctx: AccessContext = Depends(get_access_context),
):
    from app.services.followup_service import FollowupService
    svc = FollowupService()
    return [f.to_dict() for f in svc.list_for_signal(signal_id, ctx)]
