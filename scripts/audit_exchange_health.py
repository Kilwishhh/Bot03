"""Static audit: list every concrete ExchangeAdapter subclass and report
which still inherits the abstract `health_check()` instead of overriding it.

Run from the repo root:
    .venv/Scripts/python.exe scripts/audit_exchange_health.py

Exit code 0 = every concrete adapter overrides health_check.
Exit code 1 = at least one adapter needs the override.
"""

from __future__ import annotations

import inspect
import sys
from pathlib import Path

# Ensure repo root is on sys.path so `app.*` imports work without install
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.exchange.base import ExchangeAdapter  # noqa: E402


def discover_concrete_subclasses(root_cls: type) -> set[type]:
    seen: set[type] = set()
    queue: list[type] = [root_cls]
    while queue:
        current = queue.pop()
        for sub in current.__subclasses__():
            if sub in seen:
                continue
            seen.add(sub)
            queue.append(sub)
    return {c for c in seen if not inspect.isabstract(c) and c is not root_cls}


def main() -> int:
    concrete = discover_concrete_subclasses(ExchangeAdapter)
    if not concrete:
        print("WARN: no concrete ExchangeAdapter subclasses discovered", file=sys.stderr)
        return 2

    missing: list[str] = []
    for cls in sorted(concrete, key=lambda c: c.__name__):
        if cls.health_check is ExchangeAdapter.health_check:
            missing.append(cls.__name__)
            print(f"  MISSING override: {cls.__name__}")
        else:
            print(f"  OK              : {cls.__name__}")

    print()
    if missing:
        print(f"FAIL: {len(missing)} adapter(s) need health_check override:")
        for name in missing:
            print(f"  - {name}")
        return 1
    print(f"PASS: all {len(concrete)} concrete adapter(s) override health_check")
    return 0


if __name__ == "__main__":
    sys.exit(main())
