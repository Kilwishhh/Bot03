"""Validate a running API container without exchange credentials.

Covers the public surface that the rest of CI (Phase 8 release-readiness)
relies on:
- /health   liveness
- /ready    readiness
- /summary  strategy summary
- /metrics  JSON counts (Phase 4 observability)
- /prom/metrics  Prometheus exposition (Phase 4 observability, optional extra)
- /signals  read-only listing (Phase 7 API read-only)
- /trades   read-only listing
- /orders   read-only listing

Each endpoint is exercised with a 10-second timeout. The Prometheus check is
skipped (not failed) if the route is not registered (e.g., prometheus_client
extra not installed).
"""

import json
import os
import urllib.request


def _get(path: str, base_url: str) -> tuple[int, str]:
    try:
        with urllib.request.urlopen(base_url + path, timeout=10) as response:
            return response.status, response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, ""
    except Exception as e:
        return 0, f"transport_error: {e}"


def main() -> None:
    base_url = os.getenv("SMOKE_BASE_URL", "http://127.0.0.1:8000")

    # Endpoints that MUST return 200 in any environment.
    must_200 = ("/health", "/ready", "/summary", "/metrics")
    for path in must_200:
        status, body = _get(path, base_url)
        if status != 200:
            raise SystemExit(f"smoke failed: {path} returned {status} (body={body[:200]})")
        print(f"{path} ok ({len(body)} bytes)")

    # Read-only list endpoints: 200 in normal mode, 401/403 if auth is required
    # (which is also a valid response — the route is registered, not 404).
    list_endpoints = ("/signals", "/trades", "/orders")
    for path in list_endpoints:
        status, body = _get(path, base_url)
        if status == 404:
            raise SystemExit(f"smoke failed: {path} returned 404 (route not registered)")
        if status not in (200, 401, 403):
            raise SystemExit(f"smoke failed: {path} returned {status} (body={body[:200]})")
        print(f"{path} ok status={status}")

    # Prometheus exposition: optional — skip silently if not registered.
    status, body = _get("/prom/metrics", base_url)
    if status == 200:
        # Validate it actually looks like Prometheus exposition.
        if "# HELP" not in body and "# TYPE" not in body:
            raise SystemExit(
                f"smoke failed: /prom/metrics returned 200 but not prometheus-format "
                f"(first 200 chars: {body[:200]})"
            )
        print(f"/prom/metrics ok ({len(body)} bytes)")
    elif status == 404:
        print("/prom/metrics skipped (prometheus_client not installed)")
    else:
        raise SystemExit(f"smoke failed: /prom/metrics returned {status}")

    print("smoke_ok=True")


if __name__ == "__main__":
    main()
