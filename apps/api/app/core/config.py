from functools import lru_cache

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_DATABASE_URL = "postgresql+asyncpg://bot03:bot03@localhost:5432/bot03"
DEFAULT_REDIS_URL = "redis://localhost:6379/0"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "Bot03 API"
    environment: str = "development"
    debug: bool = False

    api_host: str = "0.0.0.0"
    api_port: int = 8000

    database_url: str = DEFAULT_DATABASE_URL
    redis_url: str = DEFAULT_REDIS_URL

    secret_key: str = Field(default="changeme")

    log_level: str = "INFO"

    @model_validator(mode="after")
    def _fail_on_default_secret_in_production(self) -> "Settings":
        if self.environment.lower() == "production" and self.secret_key == "changeme":
            raise ValueError("SECRET_KEY must be set when ENVIRONMENT=production")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
