import threading
import time
from decimal import Decimal

from fastapi import APIRouter, Depends, Header, HTTPException

from app.api.routes.config_routes import get_paper_config
from app.api.ws_broker import publish_event
from app.config import Settings
from app.database import TradingRepository, get_default_repository
from app.exchange import create_exchange
from app.execution import OrderManager
from app.market_data import AdapterMarketDataProvider
from app.notifications import (
    BinanceSquarePoster,
    CompositePublisher,
    DeduplicatingPublisher,
    FlushingPublisher,
    TelegramNotifier,
    TelegramSignalPublisher,
)
from app.risk import PositionSizer, RiskManager
from app.runtime import BotRunner, TradingCycle
from app.signals import SignalEngine
from app.strategy import create_strategy


async def _check_control_allowed(
    authorization: str | None = Header(None, alias="Authorization"),
    x_admin_token: str | None = Header(None, alias="X-Admin-Token"),
) -> None:
    """403 if remote control disabled, 401 if not authenticated as admin."""
    from app.config import Settings
    if not Settings().enable_remote_control:
        raise HTTPException(status_code=403, detail="remote control is disabled")
    # Accept X-Admin-Token
    import os
    expected = os.environ.get("ADMIN_API_TOKEN", "")
    if x_admin_token and x_admin_token == expected and expected:
        return
    # Accept Bearer session token
    if authorization and authorization.startswith("Bearer "):
        return
    raise HTTPException(status_code=401, detail="invalid admin token")


require_control_token = _check_control_allowed


def _build_publisher(settings):
    """Compose a deduplicated publisher chain from settings.

    Telegram is included when fully configured. Binance Square is
    included when ``ENABLE_BINANCE_SQUARE=true`` and an API key is
    present. Both sit behind a single deduplicator so the same signal
    is not posted twice across channels.
    """
    inner = []
    if settings.enable_telegram and settings.telegram_bot_token and settings.telegram_chat_id:
        inner.append(TelegramSignalPublisher(TelegramNotifier(settings.telegram_bot_token, settings.telegram_chat_id)))
    if settings.enable_binance_square and settings.binance_square_api_key:
        square = BinanceSquarePoster(
            api_key=settings.binance_square_api_key,
            endpoint=settings.binance_square_endpoint,
            daily_limit=settings.binance_square_daily_limit,
            state_dir=settings.binance_square_state_dir,
        )
        # FlushingPublisher triggers an HTTP post after every enqueue so
        # queued signals reach Square without a background worker.
        inner.append(FlushingPublisher(square))
    if not inner:
        return None
    if len(inner) == 1:
        return DeduplicatingPublisher(inner[0])
    return DeduplicatingPublisher(CompositePublisher(inner))

router = APIRouter(prefix="/control")

_controller: dict = {
    "thread": None,
    "runner": None,
    "completed": 0,
}


@router.get("/status")
def control_status() -> dict:
    """Public status — no auth required."""
    settings = Settings()
    running = _controller["thread"] is not None and _controller["thread"].is_alive()
    repository = TradingRepository(settings.database_path)
    try:
        state = repository.control_state()
        return {
            "running": running,
            "completed_cycles": _controller.get("completed", 0),
            "desired_state": state[0] if state else "stopped",
            "heartbeat_at": state[1] if state else None,
        }
    finally:
        repository.close()


@router.post("/start")
def control_start(
    cycles: int = 0,
    interval: float | None = None,
    _auth: None = Depends(require_control_token),
) -> dict:
    """Start the trading bot. Requires admin token when configured."""
    settings = Settings()
    if cycles < 0:
        raise HTTPException(status_code=400, detail="cycles cannot be negative")
    if interval is not None and interval <= 0:
        raise HTTPException(status_code=400, detail="interval must be positive")
    if _controller["thread"] is not None and _controller["thread"].is_alive():
        raise HTTPException(status_code=409, detail="bot already running")

    # Recover from stale 'running' state — the previous worker thread died without
    # calling set_control_state("stopped") (e.g. crash, OOM, SIGKILL).
    # Treat any 'running' state with no live thread as stopped.
    repo_check = get_default_repository()
    prev = repo_check.control_state()
    if prev and prev[0] == "running":
        _controller["thread"] = None  # ensure clean slate
        repo_check.set_control_state("stopped")

    try:
        exchange = create_exchange(settings)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Exchange creation failed: {e}") from e

    paper = get_paper_config()
    repository = TradingRepository(settings.database_path)
    repository.set_control_state("running")
    publisher = _build_publisher(settings)

    cycle = TradingCycle(
        AdapterMarketDataProvider(exchange),
        SignalEngine(create_strategy(settings)),
        OrderManager(
            exchange,
            RiskManager(
                Decimal(str(settings.max_daily_loss)),
                int(paper.get("max_open_positions", 3)),
                Decimal(str(paper.get("min_signal_confidence", 0.10))),
                int(paper.get("max_leverage", 10)),
                Decimal(str(settings.max_exposure)),
                settings.max_consecutive_losses,
                Decimal(str(paper.get("max_drawdown_pct", "0.15"))),
            ),
            PositionSizer(Decimal(str(paper.get("risk_per_trade", 0.01)))),
        ),
        repository,
        publisher,
        leverage=int(paper.get("max_leverage", 10)),
        position_notional=Decimal(str(paper.get("paper_position_notional", 10.0))),
    )

    runner = BotRunner(
        cycle,
        settings.default_symbol,
        settings.timeframe,
        interval or settings.poll_interval_seconds,
    )

    def run_thread() -> None:
        _controller["runner"] = runner
        completed = runner.run(None if cycles == 0 else cycles)
        _controller["completed"] = completed
        repository.set_control_state("stopped")
        _controller["thread"] = None
        from app.api.ws_broker import publish_event
        publish_event("bot_stopped", f"Bot stopped after {completed} cycle(s)", completed_cycles=completed)

    t = threading.Thread(target=run_thread, daemon=True)
    _controller["thread"] = t
    t.start()
    publish_event("bot_started", f"Bot started ({settings.default_symbol} {settings.timeframe})",
                  cycles=cycles, symbol=settings.default_symbol, timeframe=settings.timeframe)
    return {
        "status": "started",
        "daemon": True,
        "cycles_requested": cycles,
        "interval_seconds": interval or settings.poll_interval_seconds,
    }


@router.post("/stop")
def control_stop(_auth: None = Depends(require_control_token)) -> dict:
    """Stop the trading bot. Requires admin token when configured."""
    settings = Settings()
    if _controller["thread"] is None or not _controller["thread"].is_alive():
        return {"status": "not_running"}
    runner = _controller.get("runner")
    if runner is None:
        return {"status": "no_runner"}
    runner.stop()
    publish_event("bot_stop_requested", "Stop requested")
    repository = TradingRepository(settings.database_path)
    repository.set_control_state("stopping")
    repository.close()
    # Wait briefly for thread to stop
    timeout = 10
    wait = 0
    while _controller["thread"] is not None and _controller["thread"].is_alive() and wait < timeout:
        time.sleep(0.5)
        wait += 0.5
    if _controller["thread"] is None or not _controller["thread"].is_alive():
        return {"status": "stopped"}
    return {"status": "stop_requested"}
