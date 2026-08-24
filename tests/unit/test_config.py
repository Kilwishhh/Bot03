import pytest
from app.core.config import Settings, get_settings


def test_settings_defaults() -> None:
    settings = Settings()
    assert settings.app_name == "Bot03 API"
    assert settings.environment == "development"
    assert settings.database_url.startswith("postgresql+asyncpg://")
    assert settings.redis_url.startswith("redis://")


def test_production_requires_secret() -> None:
    with pytest.raises(ValueError):
        Settings(environment="production")


def test_get_settings_is_cached() -> None:
    assert get_settings() is get_settings()
