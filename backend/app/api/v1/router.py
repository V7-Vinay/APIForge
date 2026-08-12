from typing import Any
from fastapi import APIRouter, HTTPException
from sqlalchemy import text
from app.api.v1.auth import router as auth_router
from app.api.v1.workspaces import router as workspace_router
from app.core.database import engine
from app.core.redis import get_redis

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(workspace_router)


@api_router.get("/health", tags=["system"])
async def health() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "apiforge-backend",
    }


@api_router.get("/ready", tags=["system"])
async def ready() -> dict[str, Any]:
    postgres_ok = False
    redis_ok = False

    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
        postgres_ok = True
    except Exception:
        postgres_ok = False

    try:
        await get_redis().ping()
        redis_ok = True
    except Exception:
        redis_ok = False

    if not postgres_ok or not redis_ok:
        raise HTTPException(
            status_code=503,
            detail={
                "status": "not_ready",
                "postgres": postgres_ok,
                "redis": redis_ok,
            },
        )

    return {
        "status": "ready",
        "postgres": "ok",
        "redis": "ok",
    }
