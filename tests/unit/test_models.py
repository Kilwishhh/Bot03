from app.database import models  # noqa: F401  # registers models on Base.metadata
from app.database.base import Base


def test_metadata_includes_core_tables() -> None:
    tables = Base.metadata.tables
    assert "users" in tables
    assert "organizations" in tables
    assert "memberships" in tables
