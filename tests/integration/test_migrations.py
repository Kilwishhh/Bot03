import os
import subprocess
from pathlib import Path

from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import create_async_engine

REPO_ROOT = Path(__file__).resolve().parents[2]
ALEMBIC_INI = REPO_ROOT / "infrastructure" / "migrations" / "alembic.ini"
ADMIN_DATABASE_URL = "postgresql+asyncpg://bot03:bot03@localhost:5432/postgres"
TEST_DATABASE_NAME = "bot03_test"
TEST_DATABASE_URL = f"postgresql+asyncpg://bot03:bot03@localhost:5432/{TEST_DATABASE_NAME}"


async def _ensure_test_database() -> None:
    engine = create_async_engine(ADMIN_DATABASE_URL, isolation_level="AUTOCOMMIT")
    async with engine.connect() as conn:
        exists = await conn.scalar(
            text("SELECT 1 FROM pg_database WHERE datname = :name"),
            {"name": TEST_DATABASE_NAME},
        )
        if not exists:
            await conn.execute(text(f'CREATE DATABASE "{TEST_DATABASE_NAME}"'))
    await engine.dispose()


async def test_migrations_apply_cleanly() -> None:
    await _ensure_test_database()

    env = {**os.environ, "DATABASE_URL": TEST_DATABASE_URL}
    result = subprocess.run(
        ["alembic", "-c", str(ALEMBIC_INI), "upgrade", "head"],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert result.returncode == 0, f"alembic failed:\n{result.stdout}\n{result.stderr}"

    engine = create_async_engine(TEST_DATABASE_URL)
    async with engine.connect() as conn:
        tables = await conn.run_sync(lambda sync_conn: set(inspect(sync_conn).get_table_names()))
    await engine.dispose()

    assert {"users", "organizations", "memberships"} <= tables
