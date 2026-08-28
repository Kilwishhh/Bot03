#!/usr/bin/env bash
# Helper: kill any process on port 8000, then start the server with the latest code.
# Run from the project root: ./scripts/restart_server.sh
set -e
cd "$(dirname "$0")/.."

PORT=8000
echo "[restart] killing anything on port $PORT..."
PID=$(netstat -ano | grep ":$PORT " | grep LISTENING | awk '{print $NF}' | head -1)
if [ -n "$PID" ]; then
    cmd //c "taskkill /PID $PID /F" || echo "[restart] manual kill needed for PID $PID"
    sleep 2
else
    echo "[restart] nothing listening on $PORT"
fi

echo "[restart] starting uvicorn..."
exec .venv/Scripts/uvicorn.exe app.api.server:app --host 0.0.0.0 --port $PORT --log-level info
