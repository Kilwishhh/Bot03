"""Shared test fixtures — runs before any test module imports app modules."""

import os

os.environ.setdefault("ADMIN_API_TOKEN", "test-admin-secret-token-12345")
os.environ.setdefault("CONTROL_API_TOKEN", "test-control-secret-token-67890")
os.environ.setdefault("TRADING_MODE", "paper")
os.environ.setdefault("DATABASE_PATH", ":memory:")
# Explicitly disable remote control in tests so test_remote_control_is_disabled_by_default
# is not affected by a project-level .env file that enables it.
os.environ["ENABLE_REMOTE_CONTROL"] = "false"
