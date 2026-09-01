"""Safe HTTP API foundation for the mobile application."""

import asyncio
from contextlib import asynccontextmanager
from decimal import Decimal, InvalidOperation
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Install the in-memory log buffer BEFORE any other logging config runs.
# uvicorn configures its loggers in main(); we need our handler attached
# so we can tail logs in the admin UI.
from app.utils.log_buffer import install as _install_log_buffer
_install_log_buffer()

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.auth import require_admin_token
from app.api.security import (
    HTTPSEnforcementMiddleware,
    RateLimitMiddleware,
    SecurityHeadersMiddleware,
    get_audit_logger,
)


@asynccontextmanager
async def _lifespan(app: FastAPI):
    from app.api.ws_broker import set_loop
    set_loop(asyncio.get_running_loop())
    yield
from app.config import ExchangeProvider, Settings
from app.database import TradingRepository
from app.exchange.models import OrderRequest, OrderSide, OrderType
from app.execution.dex_gate import DexOrderGate
from app.notifications import BinanceSquarePoster

STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="Crypto Trading Bot API", version="0.1.0", lifespan=_lifespan)

# Serve shared CSS/JS for the web dashboards.
if STATIC_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

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

# include prometheus endpoint if available (mounted under /prom to avoid
# collision with the legacy /metrics JSON endpoint at line ~206)
try:
    from app.api.prometheus import router as prom_router
    app.include_router(prom_router, prefix="/prom")
except Exception:
    pass

# include ermis API routes (all scoped under /auth, /admin, /strategies, etc.)
try:
    from app.api.admin_spa import router as admin_spa_router
    from app.api.routes import (
        admin_routes,
        automation_routes,
        config_routes,
        connection_routes,
        dev_routes,
        emergency_routes,
        followup_routes,
        health_routes,
        publishing_routes,
        signal_routes,
        strategy_routes,
        user_routes,
    )

    app.include_router(admin_spa_router)
    app.include_router(admin_routes.router)
    app.include_router(config_routes.router)
    app.include_router(dev_routes.router)
    app.include_router(user_routes.router)
    app.include_router(strategy_routes.router)
    app.include_router(signal_routes.router)
    app.include_router(followup_routes.router)
    app.include_router(automation_routes.router)
    app.include_router(connection_routes.router)
    app.include_router(publishing_routes.router)
    app.include_router(health_routes.router)
    app.include_router(emergency_routes.router)
except Exception as exc:
    import logging
    logging.getLogger(__name__).warning("ermis routes unavailable: %s", exc)

# Safety net: ensure dev routes are always registered even if the try block above
# silently failed (the warn-and-continue pattern swallows errors here).
# Only include if not already present.
_dev_paths = {r.path for r in app.routes if hasattr(r, "path")}
if not any("/dev/" in p for p in _dev_paths):
    try:
        from app.api.routes import dev_routes as _dev_routes
        app.include_router(_dev_routes.router)
    except Exception as _e:
        import logging
        logging.getLogger(__name__).warning("dev_routes fallback include failed: %s", _e)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in Settings().api_allowed_origins.split(",") if origin.strip()],
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)

# Security middleware: security headers, optional HTTPS enforcement, rate limit.
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(HTTPSEnforcementMiddleware, require_https=Settings().api_require_https)
app.add_middleware(RateLimitMiddleware, per_minute=Settings().api_rate_limit_per_minute)


@app.get("/ui/{full_path:path}", include_in_schema=False)
def ui_spa(full_path: str) -> FileResponse:
    """Vite + React user UI."""
    base = Path(__file__).resolve().parent.parent / "dashboard" / "dist"
    if (base / full_path).exists() and (base / full_path).is_file():
        return FileResponse(base / full_path)
    return FileResponse(base / "index.html")


@app.get("/ui", include_in_schema=False)
def ui_index() -> FileResponse:
    return FileResponse(
        Path(__file__).resolve().parent.parent / "dashboard" / "dist" / "index.html"
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


@app.get("/", include_in_schema=False)
def landing() -> FileResponse:
    return FileResponse(
        Path(__file__).resolve().parent.parent.parent
        / "dashboard" / "dist" / "index.html"
    )


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
        rows = repository._connection.execute(
            "SELECT * FROM signals ORDER BY timestamp DESC LIMIT ?", (limit,)).fetchall()
        cols = [r[1] for r in repository._connection.execute(
            "PRAGMA table_info(signals)").fetchall()]
        return [dict(zip(cols, row, strict=False)) for row in rows]
    finally:
        repository.close()


@app.get("/signals/{signal_id}")
def signal_detail(signal_id: str) -> dict[str, object]:
    raise HTTPException(status_code=404, detail="Signal not found")


@app.get("/trades")
def trades(limit: int = 20) -> list[dict[str, object]]:
    if limit < 1 or limit > 100:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 100")
    repository = TradingRepository(Settings().database_path)
    try:
        rows = repository.recent_trades(limit)
        keys = ("trade_id", "symbol", "side", "quantity", "entry_price", "exit_price", "realized_pnl", "fees", "strategy", "entry_time", "exit_time")
        return [dict(zip(keys, row, strict=False)) for row in rows]
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
        return [dict(zip(keys, row, strict=False)) for row in repository.positions()]
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
    square = _build_square_poster()
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
        "square": square.get_status(),
    }


def _build_dex_exchange(settings: Settings):
    """Construct the configured DEX adapter for admin preview/approval actions.

    Only valid when an exchange provider that supports preview/approval is
    selected. For Binance/paper adapters the endpoints reject with a 400.
    """
    if settings.exchange_provider not in (
        ExchangeProvider.HYPERLIQUID,
    ):
        raise HTTPException(
            status_code=400,
            detail="selected exchange provider does not support DEX preview/approval",
        )
    from app.exchange import create_exchange
    return create_exchange(settings)


def _build_dex_request(payload: dict) -> OrderRequest:
    """Build an OrderRequest from a JSON payload, validating numeric fields."""
    try:
        quantity = Decimal(str(payload["quantity"]))
    except (KeyError, InvalidOperation) as exc:
        raise HTTPException(status_code=400, detail="quantity is required and must be a number") from exc
    if quantity <= 0:
        raise HTTPException(status_code=400, detail="quantity must be positive")
    price_raw = payload.get("price")
    price = None
    if price_raw is not None and price_raw != "":
        try:
            price = Decimal(str(price_raw))
        except InvalidOperation as exc:
            raise HTTPException(status_code=400, detail="price must be a number") from exc
        if price <= 0:
            raise HTTPException(status_code=400, detail="price must be positive")
    return OrderRequest(
        symbol=str(payload["symbol"]),
        side=OrderSide(str(payload["side"]).upper()),
        order_type=OrderType(str(payload.get("order_type", "MARKET")).upper()),
        quantity=quantity,
        price=price,
        client_order_id=payload.get("client_order_id"),
    )


@app.post("/admin/dex/preview")
def admin_dex_preview(payload: dict, request: Request, _: None = Depends(require_admin_token)) -> dict[str, object]:
    """Preview a DEX order without placing it. Requires admin token."""
    settings = Settings()
    exchange = _build_dex_exchange(settings)
    dex_request = _build_dex_request(payload)
    gate = DexOrderGate(exchange)
    if not gate.supports_preview():
        raise HTTPException(status_code=400, detail="adapter does not support preview/approval")
    preview = exchange.preview_order(dex_request)
    _audit(
        request,
        "dex.preview",
        {"symbol": str(dex_request.symbol), "side": str(dex_request.side)},
        preview.status,
    )
    return {
        "symbol": preview.symbol,
        "side": preview.side,
        "order_type": preview.order_type,
        "quantity": str(preview.quantity),
        "price": str(preview.price) if preview.price is not None else None,
        "requires_approval": preview.requires_approval,
        "status": preview.status,
        "wallet_address": preview.wallet_address,
        "client_order_id": preview.client_order_id,
    }


@app.post("/admin/dex/approve")
def admin_dex_approve(payload: dict, request: Request, _: None = Depends(require_admin_token)) -> dict[str, object]:
    """Record the wallet owner's approval of a previously-returned preview.

    The caller (typically the admin UI backed by a WalletConnect session) is
    responsible for having received real wallet-owner consent before invoking
    this endpoint.
    """
    settings = Settings()
    exchange = _build_dex_exchange(settings)
    dex_request = _build_dex_request(payload)
    gate = DexOrderGate(exchange)
    if not gate.supports_preview():
        raise HTTPException(status_code=400, detail="adapter does not support preview/approval")
    preview = exchange.preview_order(dex_request)
    exchange.approve_order(preview)
    _audit(
        request,
        "dex.approve",
        {"client_order_id": preview.client_order_id, "wallet": preview.wallet_address},
        "approved",
    )
    return {
        "approved": True,
        "client_order_id": preview.client_order_id,
        "wallet_address": preview.wallet_address,
    }


@app.post("/admin/dex/place")
def admin_dex_place(payload: dict, request: Request, _: None = Depends(require_admin_token)) -> dict[str, object]:
    """Preview, mark approved, then place a DEX order. Admin-only."""
    settings = Settings()
    exchange = _build_dex_exchange(settings)
    dex_request = _build_dex_request(payload)
    gate = DexOrderGate(exchange)
    if not gate.supports_preview():
        raise HTTPException(status_code=400, detail="adapter does not support preview/approval")
    result = gate.approve_and_place(dex_request)
    _audit(
        request,
        "dex.place",
        {"symbol": str(dex_request.symbol), "side": str(dex_request.side)},
        f"order_id={result.order_id} status={result.status}",
    )
    return {
        "order_id": result.order_id,
        "symbol": result.symbol,
        "status": result.status,
        "executed_quantity": str(result.executed_quantity),
        "average_price": str(result.average_price) if result.average_price is not None else None,
    }


def _build_square_poster() -> BinanceSquarePoster:
    """Construct a BinanceSquarePoster using the configured settings.

    The poster is always created (it works without an API key — it just
    queues messages). The daily limit and endpoint are read from the
    live settings so an admin can change them without restarting.
    """
    settings = Settings()
    return BinanceSquarePoster(
        api_key=settings.binance_square_api_key,
        endpoint=settings.binance_square_endpoint,
        daily_limit=settings.binance_square_daily_limit,
        state_dir=settings.binance_square_state_dir,
    )


def _audit(request: Request, action: str, detail: dict, result: str) -> None:
    """Write a privileged-action entry to the audit log.

    The actor is recorded as the client IP (no real identity exists yet);
    this still gives operators a way to correlate a flood of admin calls
    with a single caller. The function never raises.
    """
    actor = request.client.host if request.client else "unknown"
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        actor = forwarded.split(",")[0].strip() or actor
    get_audit_logger().record(actor=actor, action=action, detail=detail, result=result)


@app.get("/admin/square/status")
def admin_square_status(_: None = Depends(require_admin_token)) -> dict[str, object]:
    """Return the Binance Square poster's status, queue, and toggle state."""
    settings = Settings()
    poster = _build_square_poster()
    return {
        "configured": bool(settings.binance_square_api_key),
        "enabled": poster.is_posting_enabled(),
        "status": poster.get_status(),
    }


@app.post("/admin/square/toggle")
def admin_square_toggle(payload: dict, request: Request, _: None = Depends(require_admin_token)) -> dict[str, object]:
    """Turn Binance Square posting ON or OFF. Persisted to disk."""
    if "enabled" not in payload:
        raise HTTPException(status_code=400, detail="enabled (bool) is required")
    poster = _build_square_poster()
    new_state = poster._state.toggle(bool(payload["enabled"]))
    _audit(request, "square.toggle", {"enabled": new_state}, "ok")
    return {"enabled": new_state, "configured": poster.api_available}


@app.post("/admin/square/enqueue")
def admin_square_enqueue(payload: dict, request: Request, _: None = Depends(require_admin_token)) -> dict[str, object]:
    """Manually add a post to the queue (does NOT post it)."""
    message = str(payload.get("message", "")).strip()
    if not message:
        raise HTTPException(status_code=400, detail="message is required")
    priority = int(payload.get("priority", 5))
    category = str(payload.get("category", "manual"))
    poster = _build_square_poster()
    poster.enqueue(message, priority=priority, category=category)
    _audit(request, "square.enqueue", {"category": category, "priority": priority}, "ok")
    return {"queued": True, "status": poster.get_status()}


@app.post("/admin/square/flush")
def admin_square_flush(payload: dict, request: Request, _: None = Depends(require_admin_token)) -> dict[str, object]:
    """Flush up to ``count`` queued posts (default 1). Returns the flush summary."""
    count = int(payload.get("count", 1)) if payload else 1
    poster = _build_square_poster()
    result = poster.flush_queue(count=count)
    _audit(request, "square.flush", {"count": count}, f"posted={result['posted']}")
    return result


@app.get("/admin/audit/tail")
def admin_audit_tail(limit: int = 50, _: None = Depends(require_admin_token)) -> dict[str, object]:
    """Return the most recent audit-log entries (newest last)."""
    limit = max(1, min(limit, 500))
    return {"entries": get_audit_logger().tail(limit=limit), "limit": limit}
