"""Validate a running API container without exchange credentials."""

import json
import os
import urllib.request


def main() -> None:
    base_url = os.getenv("SMOKE_BASE_URL", "http://127.0.0.1:8000")
    for path in ("/health", "/ready", "/summary"):
        with urllib.request.urlopen(base_url + path, timeout=10) as response:
            payload = json.loads(response.read())
            if response.status != 200:
                raise SystemExit(f"smoke failed: {path}")
            print(f"{path} ok {payload}")


if __name__ == "__main__":
    main()
