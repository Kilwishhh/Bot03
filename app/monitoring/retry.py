"""Retry helpers for idempotent reads only."""

import time
from collections.abc import Callable
from typing import TypeVar

Result = TypeVar("Result")


def retry_read(operation: Callable[[], Result], attempts: int = 3, delay_seconds: float = 0.25) -> Result:
    """Retry an idempotent read with exponential backoff."""
    if attempts < 1 or delay_seconds < 0:
        raise ValueError("attempts must be positive and delay cannot be negative")
    for attempt in range(attempts):
        try:
            return operation()
        except Exception:
            if attempt == attempts - 1:
                raise
            time.sleep(delay_seconds * (2 ** attempt))
    raise RuntimeError("unreachable")
