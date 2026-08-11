from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1.router import api_router
from app.core.config import settings
from app.core.database import close_database, init_database
from app.core.logging import configure_logging
from app.core.redis import close_redis, init_redis


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    await init_database()
    await init_redis()
    yield
    await close_redis()
    await close_database()


app = FastAPI(
    title=settings.APP_NAME,
    version="0.2.0",
    description="APIForge collaborative API development platform.",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.API_V1_PREFIX)


@app.get("/", tags=["system"])
async def root() -> dict[str, str]:
    return {
        "name": settings.APP_NAME,
        "version": "0.2.0",
        "status": "running",
    }
