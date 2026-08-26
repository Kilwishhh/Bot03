from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.database import TradingRepository
import asyncio
import json

router = APIRouter()

@router.websocket('/ws')
async def websocket_endpoint(websocket: WebSocket):
    """Simple read-only websocket that streams recent signals and bot events.
    This is safe: it never accepts commands from the client and only publishes recent records.
    """
    await websocket.accept()
    repository = TradingRepository()
    try:
        # send initial recent signals
        rows = repository._connection.execute("SELECT symbol, side, confidence, timestamp, strategy, reason FROM signals ORDER BY timestamp DESC LIMIT 20").fetchall()
        initial = [ {"symbol": r[0], "side": r[1], "confidence": r[2], "timestamp": r[3], "strategy": r[4], "reason": r[5]} for r in rows ]
        await websocket.send_text(json.dumps({"type": "initial_signals", "data": initial}))

        last_event_id_row = repository._connection.execute("SELECT MAX(event_id) FROM bot_events").fetchone()
        last_event_id = int(last_event_id_row[0]) if last_event_id_row and last_event_id_row[0] is not None else 0

        # loop and poll for new events
        while True:
            await asyncio.sleep(2)
            rows = repository._connection.execute("SELECT event_id, event_type, message, created_at FROM bot_events WHERE event_id > ? ORDER BY event_id ASC", (last_event_id,)).fetchall()
            if rows:
                msgs = [{"event_id": r[0], "type": r[1], "message": r[2], "created_at": r[3]} for r in rows]
                last_event_id = rows[-1][0]
                await websocket.send_text(json.dumps({"type": "events", "data": msgs}))
    except WebSocketDisconnect:
        return
    except Exception as e:
        try:
            await websocket.send_text(json.dumps({"type": "error", "message": str(e)}))
        except Exception:
            pass
    finally:
        repository.close()
