from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1.router import api_router
from app.core.config import settings
from app.core.database import close_database, init_database
from app.core.logging import configure_logging
from app.core.redis import close_redis, init_redis
from app.core.errors import (
    APIError,
    api_error_handler,
    http_exception_handler,
    validation_exception_handler,
    global_exception_handler,
)
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException


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
    version="0.4.0",
    description="APIForge collaborative API development platform.",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_exception_handler(APIError, api_error_handler)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, global_exception_handler)

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
        "version": "0.4.0",
        "status": "running",
    }
