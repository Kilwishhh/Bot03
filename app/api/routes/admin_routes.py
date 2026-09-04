"""Admin routes: /admin/users/*, /admin/audit/*."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.core.errors import ForbiddenError, NotFoundError
from app.core.rbac import AccessContext
from app.strategy.condition_engine import is_valid_timeframe

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users")
def list_users(
    ctx: AccessContext = Depends(__import__("app.api.dependencies", fromlist=["get_access_context"]).get_access_context),
):
    from app.services.user_service import UserService
    svc = UserService()
    try:
        users = svc.list_users(ctx)
        return [{"id": u.id, "email": u.email, "display_name": u.display_name,
                 "role": str(u.role), "status": str(u.status),
                 "created_at": u.created_at.isoformat() if hasattr(u.created_at, "isoformat") else u.created_at}
                for u in users]
    except ForbiddenError as e:
        raise HTTPException(status_code=403, detail=e.message)


@router.get("/users/{user_id}")
def get_user(
    user_id: str,
    ctx: AccessContext = Depends(__import__("app.api.dependencies", fromlist=["get_access_context"]).get_access_context),
):
    from app.services.user_service import UserService
    svc = UserService()
    try:
        users = svc.list_users(ctx)
        for u in users:
            if u.id == user_id:
                return {"id": u.id, "email": u.email, "display_name": u.display_name,
                        "role": str(u.role), "status": str(u.status),
                        "created_at": u.created_at.isoformat()}
        raise HTTPException(status_code=404, detail="user not found")
    except ForbiddenError as e:
        raise HTTPException(status_code=403, detail=e.message)


@router.post("/users/{user_id}/suspend")
def suspend_user(
    user_id: str,
    ctx: AccessContext = Depends(__import__("app.api.dependencies", fromlist=["get_access_context"]).get_access_context),
):
    from app.services.user_service import UserService
    svc = UserService()
    try:
        u = svc.suspend_user(user_id, ctx)
        return {"id": u.id, "status": str(u.status)}
    except (ForbiddenError, NotFoundError) as e:
        raise HTTPException(status_code=e.http_status, detail=e.message)


@router.get("/strategies")
def admin_list_strategies(
    state: str | None = None,
    ctx: AccessContext = Depends(__import__("app.api.dependencies", fromlist=["get_access_context"]).get_access_context),
):
    from app.database.repository import get_default_repository
    ctx.require_admin()
    repo = get_default_repository()
    if state:
        rows = repo.db.execute("SELECT * FROM strategies WHERE lifecycle_state = ?", (state,)).fetchall()
    else:
        rows = repo.db.execute("SELECT * FROM strategies").fetchall()
    return [_admin_serialize_strategy(r) for r in rows]


@router.get("/audit")
def audit_tail(
    limit: int = 50,
    action: str | None = None,
    actor_user_id: str | None = None,
    ctx: AccessContext = Depends(__import__("app.api.dependencies", fromlist=["get_access_context"]).get_access_context),
):
    from app.database.repository import get_default_repository
    ctx.require_admin()
    repo = get_default_repository()
    rows = repo.recent_audit(limit=limit, action=action, actor_user_id=actor_user_id)
    return [{"id": r[0], "actor_user_id": r[1], "actor_role": r[2],
             "action": r[3], "target_type": r[4], "target_id": r[5],
             "detail": r[6], "result": r[7], "created_at": r[8]} for r in rows]


@router.get("/system/health")
def admin_system_health(
    ctx: AccessContext = Depends(__import__("app.api.dependencies", fromlist=["get_access_context"]).get_access_context),
):
    from app.services.health_service import HealthService
    svc = HealthService()
    try:
        return svc.check_all(ctx)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/risk")
def admin_risk_snapshot(
    ctx: AccessContext = Depends(__import__("app.api.dependencies", fromlist=["get_access_context"]).get_access_context),
):
    """Return current risk-manager state for the live bot, if any."""
    from app.api.control import _controller
    ctx.require_admin()
    snapshot = {
        "bot_running": _controller.get("thread") is not None and _controller["thread"].is_alive()
                       if _controller.get("thread") else False,
        "risk": None,
    }
    runner = _controller.get("runner")
    if runner is not None and hasattr(runner, "cycle") and hasattr(runner.cycle, "orders"):
        risk = getattr(runner.cycle.orders, "risk", None)
        if risk is not None and hasattr(risk, "snapshot"):
            snapshot["risk"] = risk.snapshot()
    return snapshot


@router.post("/users/{user_id}/activate")
def activate_user(
    user_id: str,
    ctx: AccessContext = Depends(__import__("app.api.dependencies", fromlist=["get_access_context"]).get_access_context),
):
    from app.database.repository import get_default_repository
    ctx.require_admin()
    repo = get_default_repository()
    repo._connection.execute("UPDATE users SET status='active' WHERE id=?", (user_id,))
    return {"id": user_id, "status": "active"}


@router.delete("/users/{user_id}")
def delete_user(
    user_id: str,
    ctx: AccessContext = Depends(__import__("app.api.dependencies", fromlist=["get_access_context"]).get_access_context),
):
    ctx.require_admin()
    from app.database.repository import get_default_repository
    repo = get_default_repository()
    repo._connection.execute("DELETE FROM signal_followups WHERE signal_id IN (SELECT id FROM signals WHERE user_id=?)", (user_id,))
    repo._connection.execute("DELETE FROM signals WHERE user_id=?", (user_id,))
    repo._connection.execute("DELETE FROM users WHERE id=?", (user_id,))
    return {"id": user_id, "deleted": True}


@router.get("/strategies/{strategy_id}")
def get_strategy(
    strategy_id: str,
    ctx: AccessContext = Depends(__import__("app.api.dependencies", fromlist=["get_access_context"]).get_access_context),
):
    from app.database.repository import get_default_repository
    ctx.require_admin()
    repo = get_default_repository()
    row = repo.db.execute("SELECT * FROM strategies WHERE id = ?", (strategy_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Strategy not found")
    return _admin_serialize_strategy(row)


@router.patch("/strategies/{strategy_id}")
def admin_update_strategy(
    strategy_id: str,
    payload: dict,
    ctx: AccessContext = Depends(__import__("app.api.dependencies", fromlist=["get_access_context"]).get_access_context),
):
    """Admin-level PATCH: full schema update.

    Persists every editable column including the extended-schema JSON fields
    (universe_type, universe_config, indicators_config, conditions_config,
    confidence_config, etc.) directly via SQL so all field updates land in
    the strategies table.
    """
    import json as _json
    from datetime import UTC, datetime
    from app.database.repository import get_default_repository
    ctx.require_admin()
    repo = get_default_repository()

    row = repo.db.execute("SELECT id FROM strategies WHERE id = ?", (strategy_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Strategy not found")

    if "timeframe" in payload and not is_valid_timeframe(payload["timeframe"]):
        raise HTTPException(status_code=400, detail=f"unsupported timeframe: {payload['timeframe']}")
    if "execution_mode" in payload and payload["execution_mode"] not in ("paper", "testnet", "live"):
        raise HTTPException(status_code=400, detail=f"invalid execution_mode: {payload['execution_mode']}")
    if "universe_type" in payload and payload["universe_type"] not in (
        "all_binance_futures", "top_n_futures", "custom_watchlist"
    ):
        raise HTTPException(status_code=400, detail=f"invalid universe_type: {payload['universe_type']}")

    # Plain (non-JSON) columns
    fields = {}
    for col in ("name", "description", "market", "timeframe", "execution_mode",
                "execution_venue", "lifecycle_state", "universe_type", "notes"):
        if col in payload:
            fields[col] = payload[col]

    # JSON columns
    json_fields = {}
    for col in ("entry_config", "exit_config", "risk_config", "universe_config",
                "indicators_config", "conditions_config", "filters_config",
                "confidence_config", "confirmation_timeframes", "template_params"):
        if col in payload:
            json_fields[col] = _json.dumps(payload[col])

    set_clauses = [f"{k} = ?" for k in fields] + [f"{k} = ?" for k in json_fields]
    set_clauses.append("updated_at = ?")
    set_clauses.append("version = version + 1")
    params = list(fields.values()) + list(json_fields.values())
    params.append(datetime.now(UTC).isoformat())
    params.append(strategy_id)

    try:
        repo.db.execute(
            f"UPDATE strategies SET {', '.join(set_clauses)} WHERE id = ?",
            tuple(params),
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"update failed: {exc}")

    # Audit event
    try:
        repo.db.execute(
            "INSERT INTO strategy_lifecycle_events "
            "(strategy_id, from_state, to_state, actor_user_id, actor_role, reason, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (strategy_id, "draft", fields.get("lifecycle_state", "draft"),
             "admin", "admin", "updated", datetime.now(UTC).isoformat()),
        )
    except Exception:
        pass

    # Return the freshly-updated strategy
    row = repo.db.execute("SELECT * FROM strategies WHERE id = ?", (strategy_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Strategy not found after update")
    return _admin_serialize_strategy(row)


@router.post("/strategies/{strategy_id}/transition")
def admin_transition_strategy(
    strategy_id: str,
    payload: dict,
    ctx: AccessContext = Depends(__import__("app.api.dependencies", fromlist=["get_access_context"]).get_access_context),
):
    """Admin-level lifecycle transition. target_state ∈ {draft, paper, live, paused, archived, disabled}."""
    from app.api.routes.strategy_routes import _serialize
    from app.domain.strategy import LifecycleState
    from app.services.strategy_lifecycle import StrategyLifecycle
    from app.services.strategy_service import StrategyService
    ctx.require_admin()
    svc = StrategyService()
    lifecycle = StrategyLifecycle(svc)
    try:
        s = next((x for x in svc.list_all(ctx) if x.id == strategy_id), None)
        if s is None:
            raise HTTPException(status_code=404, detail="Strategy not found")
        target = LifecycleState(payload["target_state"])
        result = lifecycle.transition(
            s, target, ctx,
            reason=payload.get("reason"),
            confirm_live=payload.get("confirm_live", False),
            confirmation_string=payload.get("confirmation_string", ""),
        )
        return _serialize(result)
    except HTTPException:
        raise
    except Exception as e:
        if hasattr(e, "http_status"):
            raise HTTPException(status_code=e.http_status, detail=e.message)
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/control")
def admin_control(
    ctx: AccessContext = Depends(__import__("app.api.dependencies", fromlist=["get_access_context"]).get_access_context),
):
    ctx.require_admin()
    from app.api.control import _controller
    from app.database.repository import get_default_repository
    repo = get_default_repository()
    state = repo.control_state()
    db_state = state[0] if state else "stopped"
    thread = _controller.get("thread")
    thread_alive = thread is not None and thread.is_alive()
    runner = _controller.get("runner")
    # Effective state — based on what the worker is actually doing
    if not thread_alive:
        effective = "stopped"
        paused = False
    elif db_state == "stopped" or _controller.get("stop"):
        effective = "stopping"
        paused = False
    elif runner is not None and runner.is_paused:
        effective = "paused"
        paused = True
    else:
        effective = "running"
        paused = False
    return {
        "state": effective,
        "db_state": db_state,
        "bot_running": thread_alive,
        "paused": paused,
    }


@router.post("/control/{action}")
def admin_control_action(
    action: str,
    ctx: AccessContext = Depends(__import__("app.api.dependencies", fromlist=["get_access_context"]).get_access_context),
):
    ctx.require_admin()
    from app.api.control import _controller
    from app.database.repository import get_default_repository
    from app.api.ws_broker import publish_event
    from datetime import UTC, datetime
    import uuid
    repo = get_default_repository()

    if action == "start":
        _controller["stop"] = False
        # Recover from stale 'running' state — the previous worker thread died
        # without updating control_state (e.g. crash, OOM, process killed).
        # Treat any 'running' row with no live thread as stopped.
        prev = repo.control_state()
        prev_state = prev[0] if prev else "stopped"
        prev_thread_alive = _controller.get("thread") is not None and _controller["thread"].is_alive()
        if prev_state == "running" and not prev_thread_alive:
            try:
                repo.set_control_state("stopped")
            except Exception:
                pass
            prev_state = "stopped"
        if _controller.get("thread") is not None and _controller["thread"].is_alive():
            return {"action": "start", "state": "running", "already": True}
        # Use the new multi-symbol scanner path
        try:
            from app.config import Settings
            from app.database import TradingRepository
            from app.database.repository import get_default_repository
            import app.exchange as _exchange_mod
            from app.market_data import AdapterMarketDataProvider
            from app.runtime import MultiSymbolRunner
            from app.strategy.scanner import StrategyScanner
            from app.api.routes.config_routes import get_paper_config
            settings = Settings()
            try:
                exchange = _exchange_mod.create_exchange(settings)
            except Exception as e:
                import traceback
                publish_event("bot_start_failed", f"Exchange creation failed: {e}\n{traceback.format_exc()}")
                raise HTTPException(status_code=400, detail=f"Exchange creation failed: {e}") from e
            # Use the default (test-patched) repository so state writes are visible to the
            # requester — the test fixture rewrites TradingRepository to point at the per-test DB.
            repository = get_default_repository()
            try:
                repository.set_control_state("running")
            except Exception as e:
                import traceback as _tb
                publish_event("bot_start_failed", f"set_control_state failed: {e}\n{_tb.format_exc()}")
                raise HTTPException(status_code=500, detail=f"set_control_state failed: {e}") from e
            market_data = AdapterMarketDataProvider(exchange)
            # P0-02: load minimum_hits from paper config
            _paper_cfg = get_paper_config()
            _min_hits = int(_paper_cfg.get("minimum_hits", 1))
            try:
                scanner = StrategyScanner(repository, market_data, minimum_hits=_min_hits)
            except Exception as e:
                import traceback as _tb
                publish_event("bot_start_failed", f"StrategyScanner init failed: {e}\n{_tb.format_exc()}")
                raise HTTPException(status_code=500, detail=f"StrategyScanner init failed: {e}") from e
            interval = settings.poll_interval_seconds

            # P0-EXEC: build the real execution pipeline so scanner signals
            # reach OrderManager → PaperTradingAdapter → DB. This is the
            # bridge that turns scanner signals into real paper trades.
            from app.execution.scanner_bridge import ScannerExecutionBridge
            from app.execution import OrderManager
            from app.risk import PositionSizer, RiskManager
            from decimal import Decimal as _D
            _max_daily_loss = _D(str(settings.max_daily_loss))
            _max_open_positions = int(_paper_cfg.get("max_open_positions", 3))
            _min_confidence = _D(str(_paper_cfg.get("min_signal_confidence", 0.10)))
            _max_leverage = int(_paper_cfg.get("max_leverage", settings.max_leverage or 10))
            _max_exposure = _D(str(settings.max_exposure)) if settings.max_exposure else None
            _max_drawdown = _D(str(_paper_cfg.get("max_drawdown_pct", "0.15")))
            _risk_per_trade = _D(str(_paper_cfg.get("risk_per_trade", 0.01)))
            _notional = _D(str(_paper_cfg.get("paper_position_notional", 10.0)))
            _risk = RiskManager(
                max_daily_loss=_max_daily_loss,
                max_open_positions=_max_open_positions,
                min_confidence=_min_confidence,
                max_leverage=_max_leverage,
                max_exposure=_max_exposure,
                max_consecutive_losses=settings.max_consecutive_losses,
                max_drawdown_pct=_max_drawdown,
            )
            _sizer = PositionSizer(_risk_per_trade)
            _order_manager = OrderManager(exchange, _risk, _sizer)
            # Resolve execution mode from settings — paper/testnet/live.
            # Live is intentionally blocked at the bridge constructor.
            _exec_mode = str(getattr(settings, "trading_mode", "paper")).lower()
            if _exec_mode in ("backtest",):
                _exec_mode = "paper"
            _bridge = ScannerExecutionBridge(
                repo=repository,
                order_manager=_order_manager,
                risk=_risk,
                execution_mode=_exec_mode,
                paper_position_notional=_notional,
                leverage=_max_leverage,
            )
            try:
                runner = MultiSymbolRunner(
                    scanner,
                    interval_seconds=interval,
                    execution_bridge=_bridge,
                )
            except Exception as e:
                import traceback as _tb
                publish_event("bot_start_failed", f"MultiSymbolRunner init failed: {e}\n{_tb.format_exc()}")
                raise HTTPException(status_code=500, detail=f"MultiSymbolRunner init failed: {e}") from e

            # P0-EXEC: start PositionWatcher so TP/SL orders can fire.
            # The watcher polls Binance public ticker and calls update_market_price()
            # on the paper adapter, which triggers the adapter's conditional order engine.
            from app.execution.position_watcher import PositionWatcher
            def _record_closed_trade(position, pnl, exit_price):
                exit_time = datetime.now(UTC).isoformat()
                repository.save_trade({
                    "trade_id": str(uuid.uuid4()),
                    "symbol": position.symbol,
                    "side": position.side.value,
                    "quantity": str(position.quantity),
                    "entry_price": str(position.entry_price),
                    "exit_price": str(exit_price),
                    "realized_pnl": str(pnl),
                    "fees": "0",
                    "strategy": "multi_symbol_scanner",
                    "entry_time": exit_time,
                    "exit_time": exit_time,
                })

            def _persist_position_update(position):
                repository.save_position(position)

            _watcher = PositionWatcher(
                paper_adapter=exchange,
                poll_interval=5.0,
                on_position_closed=_record_closed_trade,
                on_position_updated=_persist_position_update,
            )
            _watcher.start()
            # Store watcher on controller so /stop can shut it down cleanly
            _controller["position_watcher"] = _watcher

            def _run():
                _controller["runner"] = runner
                import logging as _logging
                logger = _logging.getLogger("admin_bot")
                logger.info("MULTI_BOT_STARTED interval=%.1fs", interval)
                try:
                    completed = runner.run()
                    _controller["completed"] = completed
                    logger.info("MULTI_BOT_STOPPED completed=%s", completed)
                finally:
                    try:
                        repository.set_control_state("stopped")
                    except Exception:
                        pass
                    _controller["thread"] = None
                    _controller["runner"] = None
                    publish_event("bot_stopped", "Multi-symbol bot worker exited")
            import threading
            t = threading.Thread(target=_run, daemon=True, name="mktrader-multi-bot")
            _controller["thread"] = t
            t.start()
            publish_event("bot_started", "Multi-symbol strategy scanner started",
                          symbol="*", timeframe="multi")
            return {"action": "start", "state": "running", "scanner": "multi_symbol", "interval": interval}
        except HTTPException:
            raise
        except Exception as e:
            import traceback as _tb2
            publish_event("bot_start_failed", f"start failed: {e}\n{_tb2.format_exc()}")
            try:
                repo.set_control_state("stopped")
            except Exception:
                pass
            raise HTTPException(status_code=500, detail=f"start failed: {e}") from e

    if action == "stop":
        _controller["stop"] = True
        runner = _controller.get("runner")
        if runner is not None:
            runner.stop()
        # P0-EXEC: stop the position watcher so the runner thread isn't left alive
        _watcher = _controller.get("position_watcher")
        if _watcher is not None:
            try:
                _watcher.stop()
            except Exception:
                pass
            _controller["position_watcher"] = None
        try:
            repo.set_control_state("stopped")
        except Exception:
            pass
        publish_event("bot_stop_requested", "Stop requested from admin")
        # Wait briefly for the thread to exit
        import time as _time
        deadline = _time.time() + 10
        while _controller.get("thread") is not None and _controller["thread"].is_alive() and _time.time() < deadline:
            _time.sleep(0.2)
        _controller["paused"] = False
        stopped = _controller.get("thread") is None or not _controller["thread"].is_alive()
        return {"action": "stop", "state": "stopped" if stopped else "stopping"}

    if action == "pause":
        runner = _controller.get("runner")
        if runner is not None:
            runner.pause()
        _controller["paused"] = True
        try:
            repo.set_control_state("paused")
        except Exception:
            pass
        publish_event("bot_paused", "Bot paused from admin")
        return {"action": "pause", "state": "paused"}

    if action == "resume":
        runner = _controller.get("runner")
        if runner is not None:
            runner.resume()
        _controller["paused"] = False
        try:
            repo.set_control_state("running")
        except Exception:
            pass
        publish_event("bot_resumed", "Bot resumed from admin")
        return {"action": "resume", "state": "running"}

    raise HTTPException(status_code=400, detail=f"unknown action: {action}")


@router.get("/positions")
def admin_positions(
    limit: int = 100,
    ctx: AccessContext = Depends(__import__("app.api.dependencies", fromlist=["get_access_context"]).get_access_context),
):
    """Return all open positions from the repository."""
    ctx.require_admin()
    from app.database.repository import TradingRepository
    repo = TradingRepository()
    sql = ("SELECT symbol, side, quantity, entry_price, mark_price, leverage, unrealized_pnl, opened_at, updated_at "
           "FROM positions ORDER BY updated_at DESC LIMIT ?")
    cur = repo.db.execute(sql, (limit,))
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


@router.get("/trades")
def admin_trades(
    limit: int = 100,
    symbol: str | None = None,
    ctx: AccessContext = Depends(__import__("app.api.dependencies", fromlist=["get_access_context"]).get_access_context),
):
    """Return closed trades (most recent first). Optional symbol filter."""
    ctx.require_admin()
    from app.database.repository import TradingRepository
    repo = TradingRepository()
    cols_sql = ("trade_id, symbol, side, quantity, entry_price, exit_price, realized_pnl, fees, "
                "strategy, entry_time, exit_time")
    if symbol:
        sql = f"SELECT {cols_sql} FROM trades WHERE symbol LIKE ? ORDER BY exit_time DESC LIMIT ?"
        cur = repo.db.execute(sql, (f"%{symbol}%", limit))
    else:
        sql = f"SELECT {cols_sql} FROM trades ORDER BY exit_time DESC LIMIT ?"
        cur = repo.db.execute(sql, (limit,))
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


@router.post("/restart")
def admin_restart(
    ctx: AccessContext = Depends(__import__("app.api.dependencies", fromlist=["get_access_context"]).get_access_context),
):
    """Restart the runtime worker (best-effort, admin-only)."""
    ctx.require_admin()
    from app.database.repository import TradingRepository
    repo = TradingRepository()
    repo.set_control_state("stopped")
    # Best-effort: schedule a delayed resume so the worker re-ticks
    try:
        import threading
        def _resume():
            import time
            time.sleep(2)
            repo.set_control_state("running")
        threading.Thread(target=_resume, daemon=True).start()
    except Exception:
        pass
    return {"action": "restart", "state": "stopped", "scheduled_resume_in": 2}


@router.post("/risk/{action}")
def admin_risk_action(
    action: str,
    ctx: AccessContext = Depends(__import__("app.api.dependencies", fromlist=["get_access_context"]).get_access_context),
):
    """Risk-related admin actions: kill-switch, resume, reset-daily-loss, reset-drawdown."""
    ctx.require_admin()
    from app.database.repository import TradingRepository
    repo = TradingRepository()
    if action == "kill":
        repo.set_control_state("stopped")
        return {"action": "kill", "state": "stopped"}
    if action == "resume":
        repo.set_control_state("running")
        return {"action": "resume", "state": "running"}
    if action == "reset-daily-loss":
        try:
            repo.db.execute("DELETE FROM daily_loss_events WHERE event_date = date('now')")
        except Exception:
            pass
        return {"action": "reset-daily-loss", "ok": True}
    if action == "reset-drawdown":
        try:
            repo.db.execute("UPDATE control_state SET high_water_mark = 0 WHERE id = 1")
        except Exception:
            pass
        return {"action": "reset-drawdown", "ok": True}
    raise HTTPException(status_code=400, detail=f"unknown risk action: {action}")


@router.delete("/users/{user_id}")
def admin_delete_user(
    user_id: str,
    ctx: AccessContext = Depends(__import__("app.api.dependencies", fromlist=["get_access_context"]).get_access_context),
):
    """Delete (deactivate) a user. Admin only."""
    ctx.require_admin()
    from app.database.repository import TradingRepository
    repo = TradingRepository()
    existing = repo.db.execute("SELECT id FROM users WHERE id = ?", (user_id,)).fetchone()
    if not existing:
        raise HTTPException(status_code=404, detail="user not found")
    # Soft-delete: mark status=deleted (preserve audit trail)
    try:
        repo.db.execute(
            "UPDATE users SET status = 'deleted' WHERE id = ?", (user_id,)
        )
    except Exception:
        # fallback: hard delete
        repo.db.execute("DELETE FROM users WHERE id = ?", (user_id,))
    return {"deleted": user_id}


@router.get("/logs")
def admin_logs(
    limit: int = 100,
    since: str | None = None,
    ctx: AccessContext = Depends(__import__("app.api.dependencies", fromlist=["get_access_context"]).get_access_context),
):
    """Return the most recent server log lines (in-memory ring buffer)."""
    from app.utils.log_buffer import tail
    ctx.require_admin()
    return tail(n=limit, since=since)


def reset_mode_data(repo, mode: str) -> dict[str, int | str]:
    """Delete runtime records for one mode or all modes from the repository.

    Strategies, users, and other modes are never touched.
    Returns a counts dict with keys *_deleted or *_error.
    """
    counts: dict[str, int | str] = {}

    def _safe_delete(table: str, where: str = "", params: tuple = ()) -> int:
        try:
            sql = f"DELETE FROM {table}" + (f" WHERE {where}" if where else "")
            cur = repo.db.execute(sql, params)
            repo.db.commit()
            return cur.rowcount if hasattr(cur, "rowcount") else 0
        except Exception as e:
            return str(e)

    def _safe_update(sql: str, params: tuple = ()) -> None:
        try:
            repo.db.execute(sql, params)
            repo.db.commit()
        except Exception:
            pass

    has_mode = False
    try:
        cur = repo.db.execute("PRAGMA table_info(signals)")
        has_mode = any(c[1] == "mode" for c in cur.fetchall())
    except Exception:
        pass

    if mode == "paper" or mode == "all":
        if has_mode:
            counts["signals_deleted"] = (
                _safe_delete("signals") if mode == "all"
                else _safe_delete("signals", "mode = ?", ("paper",))
            )
        else:
            counts["signals_deleted"] = _safe_delete("signals")
        counts["trades_deleted"] = _safe_delete("trades")
        counts["positions_deleted"] = _safe_delete("positions")
        counts["orders_deleted"] = _safe_delete("orders")
        counts["balances_deleted"] = _safe_delete("balances")
        counts["bot_events_deleted"] = _safe_delete("bot_events")
        counts["errors_deleted"] = _safe_delete("errors")
        counts["daily_pnl_deleted"] = _safe_delete("daily_pnl")
    elif mode in ("testnet", "live"):
        if has_mode:
            counts["signals_deleted"] = _safe_delete("signals", "mode = ?", (mode,))
        else:
            counts["signals_deleted"] = 0
        # Legacy: trades/positions/orders have no mode column locally;
        # only exchange-side testnet records are affected, not local ones.
        counts["trades_deleted"] = 0
        counts["positions_deleted"] = 0
        counts["orders_deleted"] = 0
        counts["balances_deleted"] = 0
        counts["bot_events_deleted"] = 0
        counts["errors_deleted"] = 0
        counts["daily_pnl_deleted"] = 0
    else:
        raise ValueError(f"unknown mode: {mode}")

    _safe_update("UPDATE control_state SET desired_state='stopped' WHERE id=1")
    return counts


@router.post("/reset/{mode}")
def admin_reset(
    mode: str,
    confirm: bool = False,
    ctx: AccessContext = Depends(__import__("app.api.dependencies", fromlist=["get_access_context"]).get_access_context),
):
    """Reset test data for one mode only. Modes: paper | testnet.

    NEVER touches strategies, users, configuration, or data of other modes.
    """
    ctx.require_admin()
    if mode not in ("paper", "testnet", "live", "all"):
        raise HTTPException(status_code=400, detail=f"unknown mode: {mode}")
    if not confirm:
        raise HTTPException(status_code=400, detail="confirm=true required")

    from app.database.repository import TradingRepository
    from app.api.control import _controller
    repo = TradingRepository()

    # Make sure the bot is not running while we wipe data
    if _controller.get("thread") is not None and _controller["thread"].is_alive():
        raise HTTPException(status_code=409, detail="stop the bot before resetting data")

    counts = reset_mode_data(repo, mode)

    from app.api.ws_broker import publish_event
    publish_event("data_reset", f"{mode} test data cleared: {counts}")
    return {"ok": True, "mode": mode, "counts": counts}


# ===========================================================================
# Admin strategy routes (the SPA uses /admin/strategies/*)
# ===========================================================================

def _admin_serialize_strategy(row: tuple) -> dict:
    """Serialize a strategies table row to the admin SPA shape."""
    import json
    def _col(idx, default=None):
        if idx < len(row):
            v = row[idx]
            if v is None:
                return default
            return v
        return default
    def _json(idx, default=None):
        raw = _col(idx)
        if not raw:
            return default if default is not None else {}
        try:
            return json.loads(raw)
        except (TypeError, ValueError):
            return default if default is not None else {}

    return {
        "id": row[0],
        "user_id": row[1],
        "name": row[2],
        "description": row[3] or "",
        "version": row[4] or 1,
        "lifecycle_state": row[5] or "draft",
        "execution_mode": row[6] or "paper",
        "execution_venue": row[7] or "binance",
        "market": row[8] or "binance_futures",
        "timeframe": row[9] or "15m",
        "entry_config": _json(10, {}),
        "exit_config": _json(11, {}),
        "risk_config": _json(12, {}),
        "template_name": row[13],
        "template_params": _json(14, {}),
        "created_at": row[15],
        "updated_at": row[16],
        # extended fields (migration 012)
        "universe_type": _col(17, "all_binance_futures") or "all_binance_futures",
        "universe_config": _json(18, {}),
        "confirmation_timeframes": _json(19, []),
        "indicators_config": _json(20, []),
        "conditions_config": _json(21, {}),
        "filters_config": _json(22, {}),
        "confidence_config": _json(23, {}),
        "notes": _col(24),
        "enabled_at": _col(25),
        "disabled_at": _col(26),
    }


@router.get("/strategies")
def admin_list_strategies(
    state: str | None = None,
    mode: str | None = None,
    market: str | None = None,
    limit: int = 100,
    offset: int = 0,
    ctx: AccessContext = Depends(__import__("app.api.dependencies", fromlist=["get_access_context"]).get_access_context),
):
    """List strategies visible to the current admin."""
    ctx.require_admin()
    from app.database.repository import get_default_repository
    repo = get_default_repository()
    try:
        cols = [r[1] for r in repo.db.execute("PRAGMA table_info(strategies)").fetchall()]
    except Exception:
        cols = []
    if not cols:
        return []
    q = "SELECT * FROM strategies WHERE 1=1"
    params: list = []
    if state:
        q += " AND lifecycle_state = ?"
        params.append(state)
    if mode:
        q += " AND execution_mode = ?"
        params.append(mode)
    if market:
        q += " AND market = ?"
        params.append(market)
    q += " ORDER BY updated_at DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    try:
        rows = repo.db.execute(q, params).fetchall()
    except Exception:
        return []
    return [_admin_serialize_strategy(r) for r in rows]


@router.get("/strategies/{strategy_id}")
def admin_get_strategy(
    strategy_id: str,
    ctx: AccessContext = Depends(__import__("app.api.dependencies", fromlist=["get_access_context"]).get_access_context),
):
    ctx.require_admin()
    from app.database.repository import get_default_repository
    repo = get_default_repository()
    row = repo.db.execute("SELECT * FROM strategies WHERE id = ?", (strategy_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="strategy not found")
    return _admin_serialize_strategy(row)


@router.post("/strategies")
def admin_create_strategy(
    payload: dict,
    ctx: AccessContext = Depends(__import__("app.api.dependencies", fromlist=["get_access_context"]).get_access_context),
):
    ctx.require_admin()
    from datetime import UTC, datetime
    import json
    import uuid
    from app.database.repository import get_default_repository
    repo = get_default_repository()

    name = (payload.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="name is required")

    strategy_id = str(uuid.uuid4())
    now = datetime.now(UTC).isoformat()

    # Use the first available admin user as owner if no user is set
    user_id = payload.get("user_id")
    if not user_id:
        row = repo.db.execute("SELECT id FROM users WHERE role='admin' AND status='active' LIMIT 1").fetchone()
        user_id = row[0] if row else "system"

    timeframe = payload.get("timeframe", "15m")
    if not is_valid_timeframe(timeframe):
        raise HTTPException(status_code=400, detail=f"unsupported timeframe: {timeframe}")

    market = payload.get("market", "binance_futures")
    mode = payload.get("execution_mode", "paper")
    if mode not in ("paper", "testnet", "live"):
        raise HTTPException(status_code=400, detail=f"invalid execution_mode: {mode}")

    universe_type = payload.get("universe_type", "all_binance_futures")
    if universe_type not in ("all_binance_futures", "top_n_futures", "custom_watchlist"):
        raise HTTPException(status_code=400, detail=f"invalid universe_type: {universe_type}")

    try:
        repo.db.execute(
            "INSERT INTO strategies ("
            "id, user_id, name, description, version, lifecycle_state, "
            "execution_mode, execution_venue, market, timeframe, "
            "entry_config, exit_config, risk_config, "
            "template_name, template_params, "
            "created_at, updated_at, "
            "universe_type, universe_config, confirmation_timeframes, "
            "indicators_config, conditions_config, "
            "filters_config, confidence_config, notes"
            ") VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                strategy_id, user_id, name, payload.get("description", ""),
                1, payload.get("lifecycle_state", "paper"),
                mode, payload.get("execution_venue", "binance"),
                market, timeframe,
                json.dumps(payload.get("entry_config", {})),
                json.dumps(payload.get("exit_config", {"take_profit_pct": 1.5, "stop_loss_pct": 0.75})),
                json.dumps(payload.get("risk_config", {"max_per_trade": 0.02, "max_open_positions": 3, "max_leverage": 10})),
                payload.get("template_name"),
                json.dumps(payload.get("template_params", {})),
                now, now,
                universe_type,
                json.dumps(payload.get("universe_config", {})),
                json.dumps(payload.get("confirmation_timeframes", [])),
                json.dumps(payload.get("indicators_config", [])),
                json.dumps(payload.get("conditions_config", {})),
                json.dumps(payload.get("filters_config", {})),
                json.dumps(payload.get("confidence_config", {"mode": "automatic", "base_confidence": 0.5})),
                payload.get("notes"),
            ),
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"create failed: {exc}")

    # Audit event
    try:
        repo.db.execute(
            "INSERT INTO strategy_lifecycle_events "
            "(strategy_id, from_state, to_state, actor_user_id, actor_role, reason, created_at) "
            "VALUES (?, NULL, ?, ?, ?, ?, ?)",
            (strategy_id, payload.get("lifecycle_state", "paper"),
             user_id, "admin", "created", now),
        )
    except Exception:
        pass

    return admin_get_strategy(strategy_id, ctx)


@router.put("/strategies/{strategy_id}")
def admin_update_strategy(
    strategy_id: str,
    payload: dict,
    ctx: AccessContext = Depends(__import__("app.api.dependencies", fromlist=["get_access_context"]).get_access_context),
):
    ctx.require_admin()
    import json
    from datetime import UTC, datetime
    from app.database.repository import get_default_repository
    repo = get_default_repository()
    row = repo.db.execute("SELECT * FROM strategies WHERE id = ?", (strategy_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="strategy not found")

    # Build dynamic UPDATE
    fields = {
        "name": payload.get("name", row[2]),
        "description": payload.get("description", row[3]),
        "market": payload.get("market", row[8]),
        "timeframe": payload.get("timeframe", row[9]),
        "execution_mode": payload.get("execution_mode", row[6]),
        "lifecycle_state": payload.get("lifecycle_state", row[5]),
        "universe_type": payload.get("universe_type", _admin_col(row, 17, "all_binance_futures")),
        "notes": payload.get("notes", _admin_col(row, 24)),
    }

    if "timeframe" in payload and not is_valid_timeframe(payload["timeframe"]):
        raise HTTPException(status_code=400, detail=f"unsupported timeframe: {payload['timeframe']}")
    if "execution_mode" in payload and payload["execution_mode"] not in ("paper", "testnet", "live"):
        raise HTTPException(status_code=400, detail=f"invalid execution_mode: {payload['execution_mode']}")

    json_fields = {}
    if "entry_config" in payload:
        json_fields["entry_config"] = json.dumps(payload["entry_config"])
    if "exit_config" in payload:
        json_fields["exit_config"] = json.dumps(payload["exit_config"])
    if "risk_config" in payload:
        json_fields["risk_config"] = json.dumps(payload["risk_config"])
    if "universe_config" in payload:
        json_fields["universe_config"] = json.dumps(payload["universe_config"])
    if "indicators_config" in payload:
        json_fields["indicators_config"] = json.dumps(payload["indicators_config"])
    if "conditions_config" in payload:
        json_fields["conditions_config"] = json.dumps(payload["conditions_config"])
    if "filters_config" in payload:
        json_fields["filters_config"] = json.dumps(payload["filters_config"])
    if "confidence_config" in payload:
        json_fields["confidence_config"] = json.dumps(payload["confidence_config"])
    if "confirmation_timeframes" in payload:
        json_fields["confirmation_timeframes"] = json.dumps(payload["confirmation_timeframes"])

    set_clauses = [f"{k} = ?" for k in fields] + [f"{k} = ?" for k in json_fields]
    set_clauses.append("updated_at = ?")
    set_clauses.append("version = version + 1")
    params = list(fields.values()) + list(json_fields.values())
    params.append(datetime.now(UTC).isoformat())
    params.append(strategy_id)
    try:
        repo.db.execute(f"UPDATE strategies SET {', '.join(set_clauses)} WHERE id = ?", tuple(params))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"update failed: {exc}")

    return admin_get_strategy(strategy_id, ctx)


@router.delete("/strategies/{strategy_id}")
def admin_delete_strategy(
    strategy_id: str,
    ctx: AccessContext = Depends(__import__("app.api.dependencies", fromlist=["get_access_context"]).get_access_context),
):
    ctx.require_admin()
    from app.database.repository import get_default_repository
    repo = get_default_repository()
    row = repo.db.execute("SELECT lifecycle_state FROM strategies WHERE id = ?", (strategy_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="strategy not found")
    if row[0] == "live":
        raise HTTPException(status_code=409, detail="cannot delete a LIVE strategy; stop it first")
    repo.db.execute("DELETE FROM strategies WHERE id = ?", (strategy_id,))
    return {"deleted": True, "id": strategy_id}


@router.post("/strategies/{strategy_id}/transition")
def admin_transition_strategy(
    strategy_id: str,
    payload: dict,
    ctx: AccessContext = Depends(__import__("app.api.dependencies", fromlist=["get_access_context"]).get_access_context),
):
    ctx.require_admin()
    from datetime import UTC, datetime
    from app.database.repository import get_default_repository
    repo = get_default_repository()
    target = payload.get("target_state")
    if target not in ("draft", "paper", "testnet", "live_eligible", "live", "paused", "stopped", "backtest"):
        raise HTTPException(status_code=400, detail=f"invalid target_state: {target}")
    row = repo.db.execute("SELECT lifecycle_state FROM strategies WHERE id = ?", (strategy_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="strategy not found")
    from_state = row[0]
    now = datetime.now(UTC).isoformat()
    # Resolve actor_user_id to an existing user; fall back to "system" so the
    # FK on strategy_lifecycle_events.actor_user_id -> users.id never fails.
    actor_user_id = ctx.user_id if getattr(ctx, "user_id", None) else "system"
    if not repo.db.execute("SELECT 1 FROM users WHERE id=?", (actor_user_id,)).fetchone():
        actor_user_id = "system"
    try:
        repo.db.execute("UPDATE strategies SET lifecycle_state = ?, updated_at = ? WHERE id = ?",
                       (target, now, strategy_id))
        repo.db.execute(
            "INSERT INTO strategy_lifecycle_events "
            "(strategy_id, from_state, to_state, actor_user_id, actor_role, reason, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (strategy_id, from_state, target, actor_user_id, ctx.role, payload.get("reason"), now),
        )
    except Exception as exc:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=f"transition failed: {exc}")
    return admin_get_strategy(strategy_id, ctx)


@router.post("/strategies/{strategy_id}/duplicate")
def admin_duplicate_strategy(
    strategy_id: str,
    payload: dict | None = None,
    ctx: AccessContext = Depends(__import__("app.api.dependencies", fromlist=["get_access_context"]).get_access_context),
):
    """Create a copy of a strategy with a new ID and (optionally) new name."""
    ctx.require_admin()
    from datetime import UTC, datetime
    import json
    import uuid
    from app.database.repository import get_default_repository
    repo = get_default_repository()
    row = repo.db.execute("SELECT * FROM strategies WHERE id = ?", (strategy_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="strategy not found")
    new_id = str(uuid.uuid4())
    new_name = (payload or {}).get("name") or f"{row[2]} (copy)"
    now = datetime.now(UTC).isoformat()
    user_id = row[1]
    try:
        repo.db.execute(
            "INSERT INTO strategies ("
            "id, user_id, name, description, version, lifecycle_state, "
            "execution_mode, execution_venue, market, timeframe, "
            "entry_config, exit_config, risk_config, "
            "template_name, template_params, "
            "created_at, updated_at, "
            "universe_type, universe_config, confirmation_timeframes, "
            "indicators_config, conditions_config, "
            "filters_config, confidence_config, notes"
            ") VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                new_id, user_id, new_name, row[3] or "",
                1, "draft",  # duplicate starts in draft
                row[6], row[7], row[8], row[9],
                row[10], row[11], row[12],
                row[13], row[14],
                now, now,
                _admin_col(row, 17, "all_binance_futures"),
                _admin_col(row, 18) or "{}",
                _admin_col(row, 19) or "[]",
                _admin_col(row, 20) or "[]",
                _admin_col(row, 21) or "{}",
                _admin_col(row, 22) or "{}",
                _admin_col(row, 23) or "{}",
                _admin_col(row, 24),
            ),
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"duplicate failed: {exc}")
    return admin_get_strategy(new_id, ctx)


@router.post("/strategies/import")
def admin_import_strategy(
    payload: dict,
    ctx: AccessContext = Depends(__import__("app.api.dependencies", fromlist=["get_access_context"]).get_access_context),
):
    """Import a strategy from a parsed paste-format dict."""
    ctx.require_admin()
    # Normalize the paste format into the standard create payload
    if "name" not in payload:
        raise HTTPException(status_code=400, detail="import: 'name' is required")
    # Map the paste format fields to internal config
    indicators: list[dict] = []
    ind = payload.get("indicators", {})
    if isinstance(ind, dict):
        if "ema_fast" in ind and "ema_slow" in ind:
            indicators.extend([
                {"type": "EMA", "enabled": True, "params": {"period": int(ind["ema_fast"])}},
                {"type": "EMA", "enabled": True, "params": {"period": int(ind["ema_slow"])}},
            ])
        if "rsi" in ind:
            indicators.append({
                "type": "RSI",
                "enabled": True,
                "params": {
                    "period": int(ind["rsi"]),
                    "overbought": int(ind.get("rsi_overbought", 70)),
                    "oversold": int(ind.get("rsi_oversold", 30)),
                },
            })
        if "macd" in ind:
            indicators.append({"type": "MACD", "enabled": True, "params": ind.get("macd", {})})
        if "bollinger" in ind:
            indicators.append({"type": "BOLLINGER", "enabled": True, "params": ind.get("bollinger", {})})
        if ind.get("volume"):
            indicators.append({"type": "VOLUME", "enabled": True, "params": {}})

    # Parse conditions from paste format
    conditions = {"logic": "all", "groups": []}
    entry = payload.get("entry", [])
    if isinstance(entry, list):
        for cond_str in entry:
            parsed = _parse_paste_condition(str(cond_str))
            if parsed:
                conditions["groups"].append({
                    "logic": "all",
                    "conditions": [parsed],
                })
    elif isinstance(entry, dict):
        for op, expr in entry.items():
            parsed = _parse_paste_condition(str(expr))
            if parsed:
                conditions["groups"].append({
                    "logic": str(op).lower(),
                    "conditions": [parsed],
                })

    exit_cfg = payload.get("exit", {})
    risk_cfg = payload.get("risk", {})
    confidence_cfg = payload.get("confidence", {})

    create_payload = {
        "name": payload["name"],
        "description": payload.get("description", ""),
        "market": payload.get("market", "binance_futures"),
        "timeframe": payload.get("timeframe", "15m"),
        "execution_mode": payload.get("mode", "paper"),
        "universe_type": payload.get("universe", "all_binance_futures"),
        "universe_config": payload.get("universe_config", {}),
        "indicators_config": indicators,
        "conditions_config": conditions,
        "exit_config": {
            "take_profit_pct": float(exit_cfg.get("take_profit", exit_cfg.get("take_profit_pct", 1.5))),
            "stop_loss_pct": float(exit_cfg.get("stop_loss", exit_cfg.get("stop_loss_pct", 0.75))),
            "trailing_stop": exit_cfg.get("trailing_stop", False),
            "trailing_pct": float(exit_cfg.get("trailing_pct", 0.0)),
        },
        "risk_config": {
            "max_per_trade": float(risk_cfg.get("risk_per_trade", risk_cfg.get("max_per_trade", 0.02))),
            "max_open_positions": int(risk_cfg.get("max_open_positions", 3)),
            "max_leverage": int(risk_cfg.get("max_leverage", 10)),
            "max_daily_loss": float(risk_cfg.get("max_daily_loss", 0.05)),
            "max_exposure": float(risk_cfg.get("max_exposure", 0.5)),
        },
        "confidence_config": {
            "mode": "automatic",
            "min_confidence": float(confidence_cfg.get("minimum", 0.65)),
            "base_confidence": 0.5,
        },
        "notes": payload.get("notes", ""),
        "lifecycle_state": "paper",  # import always defaults to safe paper
    }
    return admin_create_strategy(create_payload, ctx)


def _parse_paste_condition(cond_str: str) -> dict | None:
    """Parse a single condition like 'rsi < 30' or 'price > ema(21)'."""
    import re
    s = cond_str.strip().lower()
    # Try operators in order of length to avoid < matching before <=
    for op in ("<=", ">=", "==", "crosses_above", "crosses_below", "<", ">"):
        if op in s:
            parts = s.split(op, 1)
            if len(parts) == 2:
                left = parts[0].strip()
                right = parts[1].strip()
                return {
                    "field": _resolve_paste_field(left),
                    "op": op.upper().replace("CROSSES_", "CROSSES_"),
                    "value": _resolve_paste_value(right),
                    "ref": _resolve_paste_field(right) if "crosses" in op.lower() else None,
                }
    return None


def _resolve_paste_field(name: str) -> str:
    """Resolve a paste-format field name to canonical form."""
    n = name.strip().lower()
    n = n.replace("(", " ").replace(")", "")
    parts = n.split()
    if not parts:
        return "PRICE"
    base = parts[0]
    rest = " ".join(parts[1:])
    if base == "rsi":
        period = rest or "14"
        return f"RSI_{period}"
    if base == "ema":
        period = rest or "21"
        return f"EMA_{period}"
    if base == "sma":
        period = rest or "20"
        return f"SMA_{period}"
    if base in ("price", "close"):
        return "PRICE"
    if base == "volume":
        return "VOLUME"
    return name.upper().replace(" ", "_")


def _resolve_paste_value(val: str) -> float:
    """Resolve a paste-format value (number or indicator name)."""
    try:
        return float(val)
    except ValueError:
        # Treat as 0 — actual cross-reference happens via 'ref'
        return 0.0


def _admin_col(row: tuple, idx: int, default=None):
    if idx < len(row):
        v = row[idx]
        if v is None:
            return default
        return v
    return default


# ===========================================================================
# Admin signals route (SPA uses /admin/signals)
# ===========================================================================

@router.get("/signals")
def admin_list_signals(
    limit: int = 50,
    strategy_id: str | None = None,
    symbol: str | None = None,
    mode: str | None = None,
    status: str | None = None,
    trading_status: str | None = None,
    ctx: AccessContext = Depends(__import__("app.api.dependencies", fromlist=["get_access_context"]).get_access_context),
):
    ctx.require_admin()
    from app.database.repository import get_default_repository
    repo = get_default_repository()
    try:
        cols = [r[1] for r in repo.db.execute("PRAGMA table_info(signals)").fetchall()]
    except Exception:
        return []
    if not cols:
        return []
    # Build query against available columns
    select_cols = [c for c in cols if c in (
        "signal_id", "id", "strategy_id", "strategy_name", "strategy",
        "symbol", "side", "timeframe", "entry", "take_profit", "stop_loss",
        "confidence", "confidence_hits", "confidence_total",
        "mode", "reasons", "reason", "indicators",
        "candle_close_time", "status", "signal_status", "trading_status",
        "telegram_status", "square_status", "user_id",
        "tp1", "tp2", "entry_price", "candle_close_epoch",
        "timestamp", "created_at", "updated_at",
    )]
    if not select_cols:
        return []
    q = f"SELECT {', '.join(select_cols)} FROM signals WHERE 1=1"
    params: list = []
    if "trading_status" in cols and not trading_status:
        q += " AND COALESCE(trading_status, '') != ?"
        params.append("rejected")
    if strategy_id and "strategy_id" in cols:
        q += " AND strategy_id = ?"
        params.append(strategy_id)
    elif strategy_id and "strategy" in cols:
        # legacy column
        q += " AND strategy = ?"
        params.append(strategy_id)
    if symbol and "symbol" in cols:
        q += " AND symbol = ?"
        params.append(symbol)
    if mode and "mode" in cols:
        q += " AND mode = ?"
        params.append(mode)
    if status and "signal_status" in cols:
        q += " AND signal_status = ?"
        params.append(status)
    if trading_status and "trading_status" in cols:
        q += " AND trading_status = ?"
        params.append(trading_status)
    if "created_at" in cols:
        q += " ORDER BY created_at DESC"
    elif "timestamp" in cols:
        q += " ORDER BY timestamp DESC"
    q += " LIMIT ?"
    params.append(limit)
    try:
        rows = repo.db.execute(q, params).fetchall()
    except Exception:
        return []
    out = []
    for r in rows:
        d = {}
        for c, v in zip(select_cols, r):
            d[c] = v
        out.append(d)
    return out


@router.get("/signals/{signal_id}")
def admin_get_signal(
    signal_id: str,
    ctx: AccessContext = Depends(__import__("app.api.dependencies", fromlist=["get_access_context"]).get_access_context),
):
    ctx.require_admin()
    from app.database.repository import get_default_repository
    from app.notifications.signal_publisher import format_signal
    repo = get_default_repository()
    cols = [r[1] for r in repo.db.execute("PRAGMA table_info(signals)").fetchall()]
    id_col = "signal_id" if "signal_id" in cols else "id"
    row = repo.db.execute(
        f"SELECT * FROM signals WHERE {id_col} = ? OR id = ? LIMIT 1",
        (signal_id, signal_id),
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="signal not found")
    result = {c: v for c, v in zip(cols, row)}
    result["telegram_preview"] = format_signal(result)
    entry = result.get("entry_price") or result.get("entry")
    if entry is not None:
        trade = repo.db.execute(
            "SELECT trade_id, side, quantity, entry_price, exit_price, realized_pnl, fees, entry_time, exit_time "
            "FROM trades WHERE symbol = ? AND CAST(entry_price AS REAL) = CAST(? AS REAL) "
            "ORDER BY entry_time DESC LIMIT 1",
            (result.get("symbol"), entry),
        ).fetchone()
        if trade:
            result["trade"] = dict(zip(
                ("trade_id", "side", "quantity", "entry_price", "exit_price",
                 "realized_pnl", "fees", "entry_time", "exit_time"),
                trade,
            ))
    return result


# ===========================================================================
# Admin trades route (SPA uses /admin/trades)
# ===========================================================================

@router.get("/trades")
def admin_list_trades(
    limit: int = 50,
    symbol: str | None = None,
    strategy_id: str | None = None,
    ctx: AccessContext = Depends(__import__("app.api.dependencies", fromlist=["get_access_context"]).get_access_context),
):
    ctx.require_admin()
    from app.database.repository import get_default_repository
    repo = get_default_repository()
    try:
        cols = [r[1] for r in repo.db.execute("PRAGMA table_info(trades)").fetchall()]
    except Exception:
        return []
    if not cols:
        return []
    select_cols = [c for c in cols]
    q = f"SELECT {', '.join(select_cols)} FROM trades WHERE 1=1"
    params: list = []
    if symbol:
        q += " AND symbol = ?"
        params.append(symbol)
    if strategy_id and "strategy_id" in cols:
        q += " AND strategy_id = ?"
        params.append(strategy_id)
    elif strategy_id and "strategy" in cols:
        q += " AND strategy = ?"
        params.append(strategy_id)
    if "exit_time" in cols:
        q += " ORDER BY exit_time DESC"
    elif "entry_time" in cols:
        q += " ORDER BY entry_time DESC"
    q += " LIMIT ?"
    params.append(limit)
    try:
        rows = repo.db.execute(q, params).fetchall()
    except Exception:
        return []
    out = []
    for r in rows:
        d = {}
        for c, v in zip(select_cols, r):
            d[c] = v
        out.append(d)
    return out


# ===========================================================================
# Admin positions route (SPA uses /admin/positions)
# ===========================================================================

@router.get("/positions")
def admin_list_positions(
    ctx: AccessContext = Depends(__import__("app.api.dependencies", fromlist=["get_access_context"]).get_access_context),
):
    ctx.require_admin()
    from app.database.repository import get_default_repository
    repo = get_default_repository()
    try:
        cols = [r[1] for r in repo.db.execute("PRAGMA table_info(positions)").fetchall()]
    except Exception:
        return []
    if not cols:
        return []
    q = f"SELECT {', '.join(cols)} FROM positions ORDER BY symbol"
    try:
        rows = repo.db.execute(q).fetchall()
    except Exception:
        return []
    out = []
    for r in rows:
        d = {}
        for c, v in zip(cols, r):
            d[c] = v
        out.append(d)
    return out


# ===========================================================================
# Admin risk route (SPA uses /admin/risk)
# ===========================================================================

@router.get("/risk")
def admin_get_risk(
    ctx: AccessContext = Depends(__import__("app.api.dependencies", fromlist=["get_access_context"]).get_access_context),
):
    ctx.require_admin()
    from app.database.repository import get_default_repository
    from app.api.routes.config_routes import get_paper_config
    repo = get_default_repository()
    paper = get_paper_config()
    # Aggregate live state
    try:
        sig_count = int(repo.db.execute("SELECT COUNT(*) FROM signals").fetchone()[0])
    except Exception:
        sig_count = 0
    try:
        trade_count = int(repo.db.execute("SELECT COUNT(*) FROM trades").fetchone()[0])
    except Exception:
        trade_count = 0
    return {
        "paper_config": paper,
        "signal_count": sig_count,
        "trade_count": trade_count,
    }


@router.post("/risk/{action}")
def admin_risk_action(
    action: str,
    ctx: AccessContext = Depends(__import__("app.api.dependencies", fromlist=["get_access_context"]).get_access_context),
):
    ctx.require_admin()
    # Stub: pause/resume risk per action
    return {"action": action, "ok": True}


# ===========================================================================
# Admin scanner status route
# ===========================================================================

@router.get("/scanner/status")
def admin_scanner_status(
    ctx: AccessContext = Depends(__import__("app.api.dependencies", fromlist=["get_access_context"]).get_access_context),
):
    ctx.require_admin()
    from app.database.repository import get_default_repository
    repo = get_default_repository()
    try:
        active_count = int(repo.db.execute(
            "SELECT COUNT(*) FROM strategies WHERE lifecycle_state IN ('paper','testnet','live')"
        ).fetchone()[0])
    except Exception:
        active_count = 0
    try:
        total_count = int(repo.db.execute("SELECT COUNT(*) FROM strategies").fetchone()[0])
    except Exception:
        total_count = 0
    return {
        "scanner": "multi_symbol",
        "active_strategies": active_count,
        "total_strategies": total_count,
    }


# ---------------------------------------------------------------------------
# /admin/scanner/diagnostics
# ---------------------------------------------------------------------------

@router.get("/scanner/diagnostics")
def admin_scanner_diagnostics(
    ctx: AccessContext = Depends(__import__("app.api.dependencies", fromlist=["get_access_context"]).get_access_context),
):
    """Return the runtime state of the multi-symbol scanner.

    Includes the per-cycle pipeline counters (universe, candles, conditions,
    signals) so the exact stage where signal flow stops is always visible.
    """
    from app.api.control import _controller
    ctx.require_admin()

    runner = _controller.get("runner")
    scanner = getattr(runner, "_scanner", None) if runner is not None else None
    diag_snapshot = scanner.diagnostics.snapshot() if scanner is not None else {
        "running": False,
        "last_scan_at": None,
        "last_cycle": None,
        "recent_cycles": [],
        "total_signals_persisted": 0,
    }
    last_cycle = diag_snapshot.get("last_cycle") or {}

    # The currently-active strategy
    active_strategy = None
    if last_cycle.get("strategy_id"):
        try:
            from app.database.repository import get_default_repository
            repo = get_default_repository()
            row = repo.db.execute(
                "SELECT id, name, lifecycle_state, timeframe FROM strategies WHERE id = ?",
                (last_cycle["strategy_id"],),
            ).fetchone()
            if row:
                active_strategy = {
                    "id": row[0], "name": row[1],
                    "lifecycle_state": row[2], "timeframe": row[3],
                }
        except Exception:
            pass

    # Bot control state
    thread = _controller.get("thread")
    bot_running = thread is not None and thread.is_alive()
    try:
        from app.database.repository import get_default_repository
        repo = get_default_repository()
        cs = repo.control_state()
        db_state = cs[0] if cs else "stopped"
    except Exception:
        db_state = "unknown"

    # Recent signal count for cross-check
    try:
        from app.database.repository import get_default_repository
        repo = get_default_repository()
        sig_count = int(repo.db.execute("SELECT COUNT(*) FROM signals").fetchone()[0])
    except Exception:
        sig_count = 0

    return {
        "running": bot_running,
        "db_state": db_state,
        "scanner_present": scanner is not None,
        "strategies": scanner.stats.get("strategies_loaded", 0) if scanner else 0,
        "active_strategy": active_strategy,
        "last_scan_at": diag_snapshot.get("last_scan_at"),
        "symbols_loaded": last_cycle.get("symbols_loaded", 0),
        "symbols_evaluated": last_cycle.get("symbols_evaluated", 0),
        "symbols_with_valid_candles": last_cycle.get("symbols_with_candles", 0),
        "symbols_skipped": last_cycle.get("symbols_skipped", 0),
        "skip_reasons": last_cycle.get("skip_reasons", {}),
        "candles_received": last_cycle.get("symbols_with_candles", 0),
        "fresh_candles": last_cycle.get("fresh_candles", 0),
        "indicators_calculated": last_cycle.get("indicators_calculated", 0),
        "strategy_evaluations": last_cycle.get("symbols_evaluated", 0),
        "conditions_passed": last_cycle.get("conditions_passed", 0),
        "conditions_failed": last_cycle.get("conditions_failed", 0),
        "signals_created": last_cycle.get("signals_created", 0),
        "signals_persisted": last_cycle.get("signals_persisted", 0),
        "signals_deduped": last_cycle.get("signals_deduped", 0),
        "last_error": last_cycle.get("last_error"),
        "total_signals_persisted_lifetime": diag_snapshot.get("total_signals_persisted", 0),
        "signals_in_db": sig_count,
        "recent_cycles": diag_snapshot.get("recent_cycles", []),
        # P0-EXEC: execution bridge stats
        "execution": getattr(runner, "_execution_bridge", None) is not None,
        "bridge_stats": (
            runner._execution_bridge.stats
            if runner is not None and hasattr(runner, "_execution_bridge") and runner._execution_bridge is not None
            else None
        ),
        "bridge_mode": (
            runner._execution_bridge._mode
            if runner is not None and hasattr(runner, "_execution_bridge") and runner._execution_bridge is not None
            else None
        ),
    }
