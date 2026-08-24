from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.core.redis import check_redis
from app.database.session import check_database

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> JSONResponse:
    database_ok = await check_database()
    redis_ok = await check_redis()
    checks = {
        "api": "ok",
        "database": "ok" if database_ok else "error",
        "redis": "ok" if redis_ok else "error",
        "exchange": "not_configured",
        "workers": "not_configured",
    }
    status = "ok" if database_ok and redis_ok else "degraded"
    status_code = 200 if status == "ok" else 503
    return JSONResponse(
        status_code=status_code,
        content={"status": status, "checks": checks},
    )
