from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from app.api.v1.router import api_router
from app.core.config import settings
from app.core.database import close_database, init_database
from app.core.logging import configure_logging
from app.core.redis import close_redis, init_redis
from app.core.middleware import SecurityHeadersMiddleware, RequestContextMiddleware, RateLimitMiddleware, AuditLogMiddleware
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
    if settings.APP_ENV.lower() == "production":
        if len(settings.JWT_SECRET_KEY) < 32 or settings.JWT_SECRET_KEY.startswith(("dev-", "REPLACE_")):
            raise RuntimeError("JWT_SECRET_KEY must be a strong production secret.")
        if not settings.ENVIRONMENT_ENCRYPTION_KEY or settings.ENVIRONMENT_ENCRYPTION_KEY.startswith("REPLACE_"):
            raise RuntimeError("ENVIRONMENT_ENCRYPTION_KEY is required in production.")
        if not settings.COOKIE_SECURE:
            raise RuntimeError("COOKIE_SECURE must be enabled in production.")
        if settings.RATE_LIMIT_FAIL_OPEN:
            raise RuntimeError("RATE_LIMIT_FAIL_OPEN must be false in production.")
    await init_database()
    await init_redis()
    yield
    await close_redis()
    await close_database()


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="APIForge collaborative API development platform.",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_exception_handler(APIError, api_error_handler)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, global_exception_handler)

app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RequestContextMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(AuditLogMiddleware)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts)

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
        "version": settings.APP_VERSION,
        "build_sha": settings.BUILD_SHA,
        "status": "running",
    }


@app.get("/metrics", tags=["system"], response_class=PlainTextResponse, include_in_schema=False)
async def metrics() -> str:
    if not settings.METRICS_ENABLED:
        return "# Metrics disabled\n"
    from app.core.metrics import prometheus_text
    return prometheus_text()
