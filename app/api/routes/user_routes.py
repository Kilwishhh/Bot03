"""User auth routes: /auth/* + /me."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.errors import (
    ConflictError, ForbiddenError, NotFoundError, UnauthorizedError,
)
from app.core.rbac import AccessContext
from app.api.dependencies import get_access_context

router = APIRouter(tags=["auth"])


@router.post("/auth/register")
def register(payload: dict):
    from app.services.user_service import UserService
    svc = UserService()
    try:
        user = svc.register(
            email=payload.get("email", ""),
            password=payload.get("password", ""),
            display_name=payload.get("display_name"),
        )
        return {
            "id": user.id, "email": user.email,
            "display_name": user.display_name,
            "role": str(user.role), "status": str(user.status),
            "created_at": user.created_at.isoformat(),
        }
    except (ValueError, ConflictError) as e:
        raise HTTPException(status_code=409 if isinstance(e, ConflictError) else 400,
                            detail=str(e.message if hasattr(e, "message") else e))


@router.post("/auth/login")
def login(payload: dict):
    from app.services.user_service import UserService
    svc = UserService()
    try:
        user, token = svc.login(
            email=payload.get("email", ""),
            password=payload.get("password", ""),
        )
        return {
            "token": token,
            "user": {
                "id": user.id, "email": user.email,
                "display_name": user.display_name,
                "role": str(user.role), "status": str(user.status),
            },
        }
    except UnauthorizedError as e:
        raise HTTPException(status_code=401, detail=e.message)
    except ForbiddenError as e:
        raise HTTPException(status_code=403, detail=e.message)


@router.post("/auth/logout")
def logout(payload: dict, ctx: AccessContext = Depends(get_access_context)):
    from app.services.user_service import UserService
    svc = UserService()
    token = payload.get("token", "")
    if not token:
        raise HTTPException(status_code=400, detail="token required")
    svc.logout(token, ctx)
    return {"logged_out": True}


@router.get("/me")
def me(ctx: AccessContext = Depends(get_access_context)):
    return {
        "id": ctx.user.id, "email": ctx.user.email,
        "display_name": ctx.user.display_name,
        "role": str(ctx.user.role), "status": str(ctx.user.status),
        "is_admin": ctx.is_admin(),
    }


@router.get("/dashboard")
def user_dashboard(ctx: AccessContext = Depends(get_access_context)):
    """Summary: open positions, recent trades, daily PnL, active signals count."""
    from app.database import TradingRepository
    from app.config import Settings
    repo = TradingRepository(Settings().database_path)
    try:
        uid = ctx.user.id
        positions = [dict(zip(["symbol","side","quantity","entry_price","mark_price","unrealized_pnl","updated_at"], r))
                     for r in repo._connection.execute(
                         "SELECT symbol,side,quantity,entry_price,mark_price,unrealized_pnl,updated_at FROM positions"
                         ).fetchall()]
        recent_trades = repo.recent_trades(5)
        trade_keys = ("trade_id","symbol","side","quantity","entry_price","exit_price","realized_pnl","fees","strategy","entry_time","exit_time")
        trades = [dict(zip(trade_keys, r, strict=False)) for r in recent_trades
                  if r[0] and r[9] and str(r[9]) != 'paper']
        signals_count = repo._connection.execute(
            "SELECT signal_status, COUNT(*) FROM signals GROUP BY signal_status").fetchall()
        signals_breakdown = {str(r[0]): r[1] for r in signals_count}
        daily = repo._connection.execute(
            "SELECT SUM(CAST(realized_pnl AS REAL)) FROM trades WHERE CAST(entry_time AS TEXT) >= date('now')"
        ).fetchone()[0] or 0.0
        return {
            "positions": positions,
            "recent_trades": trades,
            "signals_breakdown": signals_breakdown,
            "daily_pnl": round(float(daily), 4),
        }
    finally:
        repo.close()


@router.get("/user/signals")
def user_signals(
    limit: int = 20,
    ctx: AccessContext = Depends(get_access_context),
):
    from app.services.signal_service import SignalService
    svc = SignalService()
    signals = svc.list(ctx, limit=limit)
    return [{"id": s.id, "symbol": s.symbol, "side": str(s.side), "confidence": s.confidence,
             "entry_price": s.entry_price, "tp1": s.tp1, "stop_loss": s.stop_loss,
             "signal_status": s.signal_status.value, "trading_status": s.trading_status.value,
             "created_at": s.created_at.isoformat() if s.created_at else None}
            for s in signals]


@router.get("/user/trades")
def user_trades(
    limit: int = 20,
    ctx: AccessContext = Depends(get_access_context),
):
    from app.database import TradingRepository
    from app.config import Settings
    repo = TradingRepository(Settings().database_path)
    try:
        keys = ("trade_id","symbol","side","quantity","entry_price","exit_price","realized_pnl","fees","strategy","entry_time","exit_time")
        rows = repo._connection.execute(
            "SELECT trade_id,symbol,side,quantity,entry_price,exit_price,realized_pnl,fees,strategy,entry_time,exit_time "
            "FROM trades ORDER BY entry_time DESC LIMIT ?", (limit,)).fetchall()
        return [dict(zip(keys, r, strict=False)) for r in rows]
    finally:
        repo.close()


@router.get("/user/strategies")
def user_strategies(ctx: AccessContext = Depends(get_access_context)):
    from app.services.strategy_service import StrategyService
    svc = StrategyService()
    try:
        strategies = svc.list_all(ctx)
        return [{"id": s.id, "name": s.name, "lifecycle_state": s.lifecycle_state.value,
                 "execution_mode": s.execution_mode.value, "market": s.market,
                 "updated_at": s.updated_at.isoformat() if s.updated_at else None}
                for s in strategies if s.user_id == ctx.user.id or ctx.is_admin()]
    except Exception:
        return []
