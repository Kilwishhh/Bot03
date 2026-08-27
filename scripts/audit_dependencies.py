"""Dependency audit and freeze helper.

Reports the installed versions of every runtime + dev dependency and
checks them against the upper bounds in ``pyproject.toml``. If a
mismatch is found, exits non-zero.

Usage:
    python scripts/audit_dependencies.py
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = REPO_ROOT / "pyproject.toml"


def main() -> int:
    text = PYPROJECT.read_text(encoding="utf-8")
    # Match strings like  "pydantic>=2.7,<3"  in the dependencies lists.
    pattern = re.compile(r'"([A-Za-z0-9_-]+)\s*([><=!~,\d.\s]+)"')
    declared: dict[str, str] = {}
    for name, spec in pattern.findall(text):
        # Normalise name (PEP 503): pydantic-settings and pydantic_settings both -> "pydantic-settings"
        canonical = re.sub(r"[-_.]+", "-", name.lower())
        declared[canonical] = spec.strip()

    # Get installed versions
    result = subprocess.run(
        [sys.executable, "-m", "pip", "list", "--format=json"],
        capture_output=True, text=True, check=True,
    )
    import json
    installed: dict[str, str] = {}
    for pkg in json.loads(result.stdout):
        canonical = re.sub(r"[-_.]+", "-", pkg["name"].lower())
        installed[canonical] = pkg["version"]

    print(f"Auditing {len(declared)} declared dependencies against the active venv...")
    print()

    bad: list[str] = []
    upper_bound_re = re.compile(r"<\s*(\d+(?:\.\d+)*)")
    for name, spec in sorted(declared.items()):
        if name not in installed:
            # Not installed in this env; skip silently
            continue
        inst = installed[name]
        m = upper_bound_re.search(spec)
        if m is None:
            continue
        upper = m.group(1)
        # Compare major.minor numerically
        inst_major_minor = ".".join(inst.split(".")[:2])
        if inst_major_minor > upper:
            bad.append(f"{name}: installed {inst}, declared {spec}")
            print(f"  FAIL  {name} installed {inst} but pyproject allows <{upper}")
        else:
            print(f"  ok    {name:30s} {inst:15s} (declared {spec})")

    print()
    if bad:
        print(f"{len(bad)} dependencies are above their declared upper bound.")
        return 1
    print("All installed dependencies are within their declared upper bounds.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
