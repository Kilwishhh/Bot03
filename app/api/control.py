import threading
import time
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException

from app.api.auth import require_control_token
from app.config import Settings
from app.database import TradingRepository
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

    try:
        exchange = create_exchange(settings)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Exchange creation failed: {e}") from e

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
                settings.max_open_positions,
                Decimal(str(settings.min_signal_confidence)),
                settings.max_leverage,
                Decimal(str(settings.max_exposure)),
                settings.max_consecutive_losses,
            ),
            PositionSizer(Decimal(str(settings.risk_per_trade))),
        ),
        repository,
        publisher,
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

    t = threading.Thread(target=run_thread, daemon=True)
    _controller["thread"] = t
    t.start()
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
