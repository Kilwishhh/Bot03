import structlog
from fastapi import FastAPI

from app.api.routes import health
from app.core.config import get_settings
from app.logging import configure_logging


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)
    application = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        docs_url="/docs" if settings.environment != "production" else None,
        redoc_url=None,
    )
    application.include_router(health.router)
    return application


app = create_app()

logger = structlog.get_logger()
