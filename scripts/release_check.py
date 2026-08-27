"""Release-readiness check for the local machine.

Run this before pushing to main to catch the same things CI would catch,
minus the Docker build (which needs a real Docker daemon). Exits non-zero
if anything fails.

Usage:
    python scripts/release_check.py
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
VENV_BIN = REPO_ROOT / ".venv" / "Scripts" if (REPO_ROOT / ".venv" / "Scripts").exists() else REPO_ROOT / ".venv" / "bin"
RUFF = str(VENV_BIN / ("ruff.exe" if (VENV_BIN / "ruff.exe").exists() else "ruff"))


def banner(title: str) -> None:
    print()
    print("=" * 70)
    print(title)
    print("=" * 70)


def step(title: str) -> None:
    print()
    print(f"--- {title} ---")


def ok(msg: str) -> None:
    print(f"  OK  {msg}")


def fail(msg: str) -> None:
    print(f"  FAIL {msg}")
    sys.exit(1)


def run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=str(REPO_ROOT), capture_output=True, text=True, **kwargs)


# ----------------------------------------------------------------------
# 1. Lint
# ----------------------------------------------------------------------

def check_lint() -> None:
    banner("1. Lint (ruff)")
    result = run([RUFF, "check", "app", "tests", "scripts"])
    if result.returncode != 0:
        print(result.stdout)
        print(result.stderr)
        fail("ruff found issues")
    ok("ruff passes on app/, tests/, scripts/")


# ----------------------------------------------------------------------
# 2. Pytest
# ----------------------------------------------------------------------

def check_pytest() -> None:
    banner("2. Pytest")
    result = run(["pytest", "-q", "--tb=short"])
    if result.returncode != 0:
        print(result.stdout[-2000:])
        print(result.stderr[-1000:])
        fail("pytest failed")
    ok("pytest passes")
    # Also surface the summary line
    for line in result.stdout.splitlines():
        if "passed" in line or "failed" in line:
            print(f"  {line.strip()}")


# ----------------------------------------------------------------------
# 3. Offline smoke
# ----------------------------------------------------------------------

def check_smoke() -> None:
    banner("3. Offline smoke (no network)")
    result = run(["python", "scripts/check_app.py"])
    if result.returncode != 0:
        print(result.stdout)
        print(result.stderr)
        fail("offline smoke failed")
    ok("offline smoke passes")
    for line in result.stdout.splitlines():
        if "ok=True" in line:
            print(f"  {line.strip()}")


# ----------------------------------------------------------------------
# 4. .env.example freshness
# ----------------------------------------------------------------------

def check_env_example() -> None:
    banner("4. .env.example freshness")
    example = (REPO_ROOT / ".env.example").read_text(encoding="utf-8")
    settings_file = (REPO_ROOT / "app" / "config" / "settings.py").read_text(encoding="utf-8")
    # Find every "ENV_VAR_NAME: type =" pattern in settings.
    declared = set(re.findall(r"^(\s*)([a-z_]+):\s*[A-Za-z\[\] |]+=.*$", settings_file, flags=re.MULTILINE))
    declared = {name for _, name in declared}
    documented = set(re.findall(r"^([A-Z_][A-Z0-9_]+)=", example, flags=re.MULTILINE))
    # Filter declared to all-uppercase
    declared_upper = {d.upper() for d in declared if d.islower()}
    missing = declared_upper - documented - {"PYTHON", "PIP"}
    # Also detect settings not lowercase (e.g. enum defaults)
    if missing:
        print(f"  warn: {len(missing)} settings present in app/config/settings.py but absent from .env.example:")
        for m in sorted(missing)[:20]:
            print(f"    - {m}")
    else:
        ok(".env.example covers all settings.py fields")


# ----------------------------------------------------------------------
# 5. No secrets committed
# ----------------------------------------------------------------------

def check_no_secrets() -> None:
    banner("5. No secrets in repo")
    banned = [".env", ".env.local", ".env.production"]
    for filename in banned:
        if (REPO_ROOT / filename).exists():
            fail(f"{filename} is in the repo root (should be in .gitignore)")
    ok(f"no {', '.join(banned)} committed")
    # Scan tracked files for what looks like a real API secret (placeholder
    # strings are fine; we only flag 64-char hex/b64 strings).
    secret_re = re.compile(r"\b[A-Za-z0-9+/=]{60,}\b")
    skip_dirs = {".venv", "node_modules", "build", "dist", ".git", ".pytest_cache", "__pycache__"}
    findings: list[str] = []
    for path in REPO_ROOT.rglob("*"):
        if not path.is_file():
            continue
        if any(part in skip_dirs for part in path.parts):
            continue
        if path.suffix in {".pyc", ".png", ".jpg", ".jpeg", ".gif", ".db", ".sqlite", ".sqlite3", ".lock", ".txt"}:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for match in secret_re.findall(text):
            if match in {"x" * 60, "0" * 60, "AAAA" * 16}:
                continue
            findings.append(f"{path.relative_to(REPO_ROOT)}: {match[:20]}...")
            break  # one per file is enough
    if findings:
        print("  warn: possible high-entropy strings in tracked files:")
        for f in findings[:10]:
            print(f"    - {f}")
        print("  (review manually — these may be placeholders, hashes, or real secrets)")
    else:
        ok("no high-entropy strings in tracked source")


# ----------------------------------------------------------------------
# 6. Audit log directory is writable
# ----------------------------------------------------------------------

def check_audit_dir() -> None:
    banner("6. Audit log directory")
    import os
    import tempfile
    with tempfile.TemporaryDirectory():
        # The app reads API_AUDIT_LOG_DIR from settings. Default is ./audit.
        audit_dir = REPO_ROOT / "audit"
        if audit_dir.exists() and not os.access(audit_dir, os.W_OK):
            fail(f"{audit_dir} is not writable")
        ok("audit directory is writable (or absent and will be created at startup)")


# ----------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------

def main() -> int:
    print(f"Repo: {REPO_ROOT}")
    check_lint()
    check_pytest()
    check_smoke()
    check_env_example()
    check_no_secrets()
    check_audit_dir()
    banner("All release checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
