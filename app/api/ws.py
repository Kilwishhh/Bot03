"""WebSocket endpoint — fan-out subscriber for real-time bot events."""
import asyncio
import contextlib
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.api.ws_broker import broker, encode
from app.database import TradingRepository

router = APIRouter()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Streams bot events to all connected clients. Subscribes to the
    EventBroker so callers (start/stop, cycle completions) can push updates
    without the client having to poll."""
    await websocket.accept()
    queue: asyncio.Queue = asyncio.Queue(maxsize=50)
    broker.attach(queue)

    try:
        # Send current bot status
        repo = TradingRepository()
        try:
            status = _build_status_snapshot(repo)
            await websocket.send_text(encode({"type": "status", **status}))
        finally:
            repo.close()

        # Send recent signals
        repo2 = TradingRepository()
        try:
            rows = repo2._connection.execute(
                "SELECT symbol,side,confidence,timestamp,strategy,reason "
                "FROM signals ORDER BY timestamp DESC LIMIT 20"
            ).fetchall()
            signals = [{"symbol": r[0], "side": r[1], "confidence": r[2],
                       "timestamp": r[3], "strategy": r[4], "reason": r[5]}
                      for r in rows]
            await websocket.send_text(encode({"type": "initial_signals", "data": signals}))
        finally:
            repo2.close()

        # Stream loop: drain broker queue + keepalive ping
        last_ping = asyncio.get_event_loop().time()
        while True:
            try:
                elapsed = asyncio.get_event_loop().time() - last_ping
                timeout = max(1, 30 - elapsed)
                event = await asyncio.wait_for(queue.get(), timeout=timeout)
                await websocket.send_text(encode(event))
                if event.get("type") == "ping":
                    last_ping = asyncio.get_event_loop().time()
            except asyncio.TimeoutError:
                # Keepalive ping every 30s
                await websocket.send_text(encode({"type": "ping"}))
                last_ping = asyncio.get_event_loop().time()
    except WebSocketDisconnect:
        pass
    except Exception as e:
        with contextlib.suppress(Exception):
            await websocket.send_text(encode({"type": "error", "message": str(e)}))
    finally:
        broker.detach(queue)


def _build_status_snapshot(repo: TradingRepository) -> dict:
    state = repo.control_state()
    state_value = state[0] if state else "stopped"
    return {
        "running": state_value == "running",
        "state": state_value,
        "heartbeat_at": state[1] if state else None,
    }
