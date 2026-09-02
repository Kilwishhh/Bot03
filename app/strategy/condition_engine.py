"""Entry/exit condition evaluation engine.

Evaluates structured condition groups against computed indicator values.

Condition schema (stored as JSON in strategies table):
  {
    "logic": "all" | "any",       -- AND vs OR for top-level groups
    "groups": [
      {
        "logic": "all" | "any",
        "conditions": [
          {"field": "RSI_14", "op": "<", "value": 30},
          {"field": "EMA_21", "op": ">", "value": 50000},
          {"field": "EMA_9",  "op": "CROSSES_ABOVE", "ref": "EMA_21"},
        ]
      }
    ]
  }

For CROSSES_ABOVE / CROSSES_BELOW the "value" is the current indicator value
and "ref" is the second indicator to compare against (both must be in values dict).
"""

from __future__ import annotations

import math
import operator
import re
from typing import Any, Callable

# -------------------------------------------------------------------------------------------------------------------------------------------
# Timeframe validation
# -------------------------------------------------------------------------------------------------------------------------------------------

_TF_PATTERN = re.compile(r'^(\d+)([mhdwM])$')


def is_valid_timeframe(tf: str) -> bool:
    """Return True for valid timeframe strings like '7m', '2h', '1d', '15m'."""
    if not tf:
        return False
    m = _TF_PATTERN.match(tf.strip())
    if not m:
        return False
    val = int(m.group(1))
    if val <= 0:
        return False
    return True


# -------------------------------------------------------------------------------------------------------------------------------------------
# Operator registry
# -------------------------------------------------------------------------------------------------------------------------------------------

OPS: dict[str, Callable[[float, float], bool]] = {
    ">":  operator.gt,
    "<":  operator.lt,
    ">=": operator.ge,
    "<=": operator.le,
    "==": operator.eq,
}


def _safe_float(v: Any) -> float | None:
    """Convert to float, returning None for non-numeric values."""
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Single-condition evaluation
# ---------------------------------------------------------------------------

def evaluate_condition(
    condition: dict[str, Any],
    values: dict[str, float | None],
    prev_values: dict[str, float | None] | None = None,
) -> tuple[bool, str]:
    """Evaluate one condition dict against indicator values.

    Returns (result: bool, reason: str).
    """
    field = str(condition.get("field", "")).upper()
    op    = str(condition.get("op", "")).upper()
    value = _safe_float(condition.get("value"))
    ref   = condition.get("ref")          # for CROSSES_ABOVE/BELOW

    current = values.get(field)
    if current is None:
        return False, f"{field} has no value"

    # Arithmetic comparisons
    if op in OPS:
        if value is None:
            return False, f"{field} {op} <empty>"
        fn = OPS[op]
        result = fn(current, value)
        return result, f"{field} {op} {value} (actual={current:.4f})" if result else f"{field} {op} {value} not met ({current:.4f})"

    # Cross operators
    if op == "CROSSES_ABOVE":
        ref_str = str(ref).upper() if ref else ""
        prev = (prev_values or {}).get(field)
        prev_ref = (prev_values or {}).get(ref_str)
        curr_ref = values.get(ref_str)
        if prev is None or curr_ref is None:
            return False, f"CROSSES_ABOVE needs prior values for {field} and {ref_str}"
        crossed = prev <= (prev_ref or 0) and current > (curr_ref or 0)
        return crossed, f"{field} crossed above {ref_str}" if crossed else f"{field} has not crossed above {ref_str}"

    if op == "CROSSES_BELOW":
        ref_str = str(ref).upper() if ref else ""
        prev = (prev_values or {}).get(field)
        prev_ref = (prev_values or {}).get(ref_str)
        curr_ref = values.get(ref_str)
        if prev is None or curr_ref is None:
            return False, f"CROSSES_BELOW needs prior values for {field} and {ref_str}"
        crossed = prev >= (prev_ref or 0) and current < (curr_ref or 0)
        return crossed, f"{field} crossed below {ref_str}" if crossed else f"{field} has not crossed below {ref_str}"

    return False, f"unknown operator: {op}"


# ---------------------------------------------------------------------------
# Group evaluation
# ---------------------------------------------------------------------------

def evaluate_group(
    group: dict[str, Any],
    values: dict[str, float | None],
    prev_values: dict[str, float | None] | None = None,
) -> tuple[bool, str]:
    """Evaluate a condition group.

    group = {"logic": "all"|"any", "conditions": [...]}
    Returns (result, reason).
    """
    logic = (group.get("logic") or "all").lower()
    conditions = group.get("conditions", [])

    if not conditions:
        return True, ""

    results: list[tuple[bool, str]] = []
    for cond in conditions:
        results.append(evaluate_condition(cond, values, prev_values))

    if logic == "any":
        # Short-circuit: return True on first match
        for ok, reason in results:
            if ok:
                return True, reason
        failed = [r for r, _ in results if not r]
        return False, f"no condition matched ({len(failed)} failed)"
    else:
        # All must match
        failed = [(r, msg) for r, msg in results if not r]
        if not failed:
            return True, results[0][1] if results else ""
        return False, "; ".join(msg for _, msg in failed[:3])


def evaluate_condition_groups(
    config: dict[str, Any] | None,
    values: dict[str, float | None],
    prev_values: dict[str, float | None] | None = None,
) -> tuple[bool, list[str]]:
    """Evaluate the full condition structure.

    config = {
        "logic": "all" | "any",
        "groups": [...]
    }

    Returns (matched: bool, reasons: list[str]).
    """
    if not config:
        return True, ["no conditions configured"]

    logic = (config.get("logic") or "all").lower()
    groups = config.get("groups", [])

    if not groups:
        return True, ["no condition groups"]

    group_results: list[tuple[bool, str]] = []
    for grp in groups:
        group_results.append(evaluate_group(grp, values, prev_values))

    if logic == "any":
        matched = any(ok for ok, _ in group_results)
        reasons = [msg for ok, msg in group_results if ok]
        return matched, reasons if reasons else ["no group matched"]
    else:
        matched = all(ok for ok, _ in group_results)
        reasons = [msg for ok, msg in group_results if ok]
        return matched, reasons if reasons else ["all conditions failed"]


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

SUPPORTED_FIELDS = {
    "PRICE", "OPEN", "HIGH", "LOW", "VOLUME",
}
SUPPORTED_OPS = {"<", ">", "<=", ">=", "==", "CROSSES_ABOVE", "CROSSES_BELOW"}


def validate_condition(condition: dict[str, Any]) -> list[str]:
    """Return list of validation errors for a single condition."""
    errors = []
    field = condition.get("field", "")
    op    = condition.get("op", "")
    value = condition.get("value")
    ref   = condition.get("ref")

    if not field:
        errors.append("condition missing 'field'")
    if not op:
        errors.append("condition missing 'op'")
    elif op.upper() not in SUPPORTED_OPS:
        errors.append(f"unsupported operator: {op}")

    if op.upper() in OPS:
        if value is None:
            errors.append(f"condition '{field} {op}' needs a 'value'")
        else:
            try:
                float(value)
            except (TypeError, ValueError):
                errors.append(f"condition value must be numeric, got: {value!r}")

    if op.upper() in ("CROSSES_ABOVE", "CROSSES_BELOW"):
        if not ref:
            errors.append(f"{op} requires a 'ref' field (second indicator name)")

    return errors


def validate_condition_config(config: dict[str, Any] | None) -> list[str]:
    """Validate the full condition config and return all errors."""
    if not config:
        return []
    errors: list[str] = []
    logic = config.get("logic", "all")
    if logic not in ("all", "any"):
        errors.append(f"top-level 'logic' must be 'all' or 'any', got: {logic}")
    groups = config.get("groups", [])
    for i, grp in enumerate(groups):
        grp_logic = grp.get("logic", "all")
        if grp_logic not in ("all", "any"):
            errors.append(f"group[{i}] 'logic' must be 'all' or 'any', got: {grp_logic}")
        conds = grp.get("conditions", [])
        for j, cond in enumerate(conds):
            errs = validate_condition(cond)
            for e in errs:
                errors.append(f"group[{i}].conditions[{j}]: {e}")
    return errors
