"""Safe HTTP API foundation for the mobile application."""

from fastapi import Depends, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pathlib import Path
from app.config import Settings
from app.database import TradingRepository
from app.api.auth import require_admin_token
import asyncio
import json


app = FastAPI(title="Crypto Trading Bot API", version="0.1.0")

# include websocket router (read-only)
try:
    from app.api.ws import router as ws_router
    app.include_router(ws_router)
except Exception:
    # if import fails, websocket will be unavailable but API remains functional
    pass

# include control router (start/stop) but only active when remote control enabled in settings
try:
    from app.api.control import router as control_router
    app.include_router(control_router)
except Exception:
    pass

# include prometheus endpoint if available
try:
    from app.api.prometheus import router as prom_router
    app.include_router(prom_router)
except Exception:
    pass
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in Settings().api_allowed_origins.split(",") if origin.strip()],
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/mobile", include_in_schema=False)
def mobile() -> FileResponse:
    return FileResponse(Path(__file__).with_name("mobile.html"))


@app.get("/manifest.json", include_in_schema=False)
def manifest() -> FileResponse:
    return FileResponse(Path(__file__).with_name("manifest.json"), media_type="application/manifest+json")


@app.get("/service-worker.js", include_in_schema=False)
def service_worker() -> FileResponse:
    return FileResponse(Path(__file__).with_name("service-worker.js"), media_type="application/javascript")


@app.get("/")
def root() -> dict[str, str]:
    return {"name": "Crypto Trading Bot API", "status": "ready"}


@app.get("/health")
def health() -> dict[str, object]:
    settings = Settings()
    return {"healthy": True, "mode": settings.trading_mode.value, "live_trading_enabled": settings.enable_live_trading}


@app.get("/status")
def status() -> dict[str, object]:
    settings = Settings()
    return {"mode": settings.trading_mode.value, "provider": settings.exchange_provider.value, "symbol": settings.default_symbol, "timeframe": settings.timeframe}


@app.get("/summary")
def summary() -> dict[str, object]:
    settings = Settings()
    return {
        "healthy": True,
        "mode": settings.trading_mode.value,
        "provider": settings.exchange_provider.value,
        "symbol": settings.default_symbol,
        "timeframe": settings.timeframe,
        "live_trading_enabled": settings.enable_live_trading,
        "remote_control_enabled": settings.enable_remote_control,
    }


@app.get("/ready")
def ready() -> dict[str, object]:
    settings = Settings()
    return {
        "ready": True,
        "healthy": True,
        "mode": settings.trading_mode.value,
        "provider": settings.exchange_provider.value,
        "live_trading_enabled": settings.enable_live_trading,
        "remote_control_enabled": settings.enable_remote_control,
    }


@app.get("/metrics")
def metrics() -> dict[str, int]:
    repository = TradingRepository(Settings().database_path)
    try:
        return {table: repository.count(table) for table in ("signals", "orders", "trades", "daily_pnl", "bot_events", "errors")}
    finally:
        repository.close()


@app.get("/orders")
def orders(limit: int = 20) -> list[dict[str, object]]:
    if limit < 1 or limit > 100:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 100")
    repository = TradingRepository(Settings().database_path)
    try:
        return [
            {"order_id": row[0], "symbol": row[1], "status": row[2], "quantity": row[3], "average_price": row[4], "created_at": row[5]}
            for row in repository.recent_orders(limit)
        ]
    finally:
        repository.close()


@app.get("/signals")
def signals(limit: int = 20) -> list[dict[str, object]]:
    if limit < 1 or limit > 100:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 100")
    repository = TradingRepository(Settings().database_path)
    try:
        rows = repository._connection.execute("SELECT symbol, side, confidence, timestamp, strategy, reason FROM signals ORDER BY timestamp DESC LIMIT ?", (limit,)).fetchall()
        return [{"symbol": row[0], "side": row[1], "confidence": row[2], "timestamp": row[3], "strategy": row[4], "reason": row[5]} for row in rows]
    finally:
        repository.close()


@app.get("/trades")
def trades(limit: int = 20) -> list[dict[str, object]]:
    if limit < 1 or limit > 100:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 100")
    repository = TradingRepository(Settings().database_path)
    try:
        rows = repository.recent_trades(limit)
        keys = ("trade_id", "symbol", "side", "quantity", "entry_price", "exit_price", "realized_pnl", "fees", "strategy", "entry_time", "exit_time")
        return [dict(zip(keys, row)) for row in rows]
    finally:
        repository.close()


@app.get("/balances")
def balances() -> list[dict[str, object]]:
    repository = TradingRepository(Settings().database_path)
    try:
        return [{"asset": row[0], "wallet_balance": row[1], "available_balance": row[2], "updated_at": row[3]} for row in repository.balances()]
    finally:
        repository.close()


@app.get("/positions")
def positions() -> list[dict[str, object]]:
    repository = TradingRepository(Settings().database_path)
    try:
        keys = ("symbol", "side", "quantity", "entry_price", "mark_price", "leverage", "unrealized_pnl", "updated_at")
        return [dict(zip(keys, row)) for row in repository.positions()]
    finally:
        repository.close()


def _limited_value(limit: int) -> int:
    if limit < 1 or limit > 100:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 100")
    return limit


@app.get("/events")
def events(limit: int = 20) -> list[dict[str, object]]:
    repository = TradingRepository(Settings().database_path)
    try:
        rows = repository.recent_events(_limited_value(limit))
        return [{"event_type": row[0], "message": row[1], "created_at": row[2]} for row in rows]
    finally:
        repository.close()


@app.get("/errors")
def errors(limit: int = 20) -> list[dict[str, object]]:
    repository = TradingRepository(Settings().database_path)
    try:
        rows = repository.recent_errors(_limited_value(limit))
        return [{"error_type": row[0], "message": row[1], "created_at": row[2]} for row in rows]
    finally:
        repository.close()


@app.get("/admin", include_in_schema=False)
def admin_dashboard() -> FileResponse:
    return FileResponse(Path(__file__).with_name("admin.html"))


@app.get("/admin/status")
def admin_status(_: None = Depends(require_admin_token)) -> dict[str, object]:
    settings = Settings()
    from app.api.control import control_status
    controller = control_status()
    return {
        "healthy": True,
        "running": controller["running"],
        "completed_cycles": controller["completed_cycles"],
        "mode": settings.trading_mode.value,
        "provider": settings.exchange_provider.value,
        "symbol": settings.default_symbol,
        "timeframe": settings.timeframe,
        "live_trading_enabled": settings.enable_live_trading,
        "remote_control_enabled": settings.enable_remote_control,
    }


@app.get("/admin/summary")
def admin_summary(_: None = Depends(require_admin_token)) -> dict[str, object]:
    payload = summary()
    status = admin_status()
    payload.update(status)
    return payload


@app.get("/admin/data")
def admin_data(_: None = Depends(require_admin_token)) -> dict[str, object]:
    settings = Settings()
    return {
        "status": admin_status(),
        "metrics": metrics(),
        "signals": signals(20),
        "orders": orders(20),
        "trades": trades(20),
        "balances": balances(),
        "positions": positions(),
        "events": events(20),
        "errors": errors(20),
        "risk": {
            "risk_per_trade": settings.risk_per_trade,
            "max_daily_loss": settings.max_daily_loss,
            "max_open_positions": settings.max_open_positions,
            "max_leverage": settings.max_leverage,
            "max_exposure": settings.max_exposure,
            "max_consecutive_losses": settings.max_consecutive_losses,
            "min_signal_confidence": settings.min_signal_confidence,
        },
        "dex": {
            "wallet_connected": bool(settings.hyperliquid_wallet_address),
            "wallet_address": settings.hyperliquid_wallet_address,
            "walletconnect_configured": bool(settings.walletconnect_project_id),
            "chain_configured": settings.dex_chain_id is not None and bool(settings.dex_rpc_url),
            "execution_requires_approval": True,
        },
    }