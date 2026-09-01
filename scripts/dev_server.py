"""MK TRADER dev launcher: starts uvicorn and respawns it on exit.

Usage:
    .venv/Scripts/python.exe scripts/dev_server.py

Environment:
    ADMIN_API_TOKEN   required (admin token used by the UI)
    MK_PORT           default 8000
    MK_HOST           default 127.0.0.1
    MK_DEV_LAUNCHER=1 set automatically so /admin/restart can detect us

Behaviour:
- Spawns `uvicorn app.api.server:app --host HOST --port PORT` in a subprocess.
- On exit code 0: launcher exits (clean shutdown).
- On any other exit code (or signal): respawn after 2s.
- Ctrl+C in this launcher cleanly terminates the child and exits.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOST = os.environ.get("MK_HOST", "127.0.0.1")
PORT = os.environ.get("MK_PORT", "8000")
LOG = ROOT / "logs" / "dev_server.log"
LOG.parent.mkdir(exist_ok=True)


def main() -> int:
    env = os.environ.copy()
    env["MK_DEV_LAUNCHER"] = "1"
    if not env.get("ADMIN_API_TOKEN"):
        print("WARNING: ADMIN_API_TOKEN is not set; /admin/* routes will be locked", file=sys.stderr)

    cmd = [sys.executable, "-m", "uvicorn", "app.api.server:app",
           "--host", HOST, "--port", str(PORT)]
    print(f"[dev_server] launching: {' '.join(cmd)}", flush=True)

    child: subprocess.Popen | None = None

    def term(_signo, _frame):
        if child and child.poll() is None:
            print("[dev_server] terminating child…", flush=True)
            child.terminate()
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                child.kill()

    signal.signal(signal.SIGINT, term)
    signal.signal(signal.SIGTERM, term)

    while True:
        with LOG.open("a", encoding="utf-8") as logf:
            child = subprocess.Popen(
                cmd, cwd=str(ROOT), env=env,
                stdout=logf, stderr=subprocess.STDOUT,
            )
        rc = child.wait()
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        print(f"[dev_server] {ts} child exited rc={rc}", flush=True)
        if rc == 0:
            return 0
        time.sleep(2)
        print("[dev_server] respawning…", flush=True)


if __name__ == "__main__":
    sys.exit(main() or 0)
