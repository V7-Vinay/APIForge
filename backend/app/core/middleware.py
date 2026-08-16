import time
import uuid
import logging
from contextlib import suppress

logger = logging.getLogger("app.core.middleware")

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.rate_limit import check_rate_limit
from app.core.metrics import record_request
from app.core.redaction import redact_url
from app.core.request_context import reset_request_id, set_request_id
from app.core.redis import get_redis
from app.core.security import TokenError, decode_access_token
from app.models.audit_log import AuditLog


def _client_ip(request: Request) -> str:
    # Do not trust X-Forwarded-For unless the deployment explicitly enables it.
    if settings.TRUST_PROXY_HEADERS:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",", 1)[0].strip()
    return request.client.host if request.client else "unknown"


def _identity(request: Request) -> str:
    authorization = request.headers.get("authorization", "")
    if authorization.lower().startswith("bearer "):
        try:
            payload = decode_access_token(authorization[7:].strip())
            return str(payload.get("sub", "anonymous"))
        except (TokenError, KeyError, ValueError):
            pass
    return f"ip:{_client_ip(request)}"


def _workspace_id(request: Request):
    marker = "/workspaces/"
    path = request.url.path
    if marker not in path:
        return None
    raw = path.split(marker, 1)[1].split("/", 1)[0]
    try:
        return uuid.UUID(raw)
    except ValueError:
        return None


def _resource_info(request: Request):
    parts = [part for part in request.url.path.split("/") if part]
    resource_type = None
    resource_id = None
    known = {"collections", "folders", "requests", "environments", "environment-variables", "invitations", "workspaces"}
    for index, part in enumerate(parts):
        if part in known:
            resource_type = part
            if index + 1 < len(parts):
                with suppress(ValueError):
                    resource_id = uuid.UUID(parts[index + 1])
            break
    return resource_type, resource_id


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        if settings.APP_ENV.lower() == "production":
            response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        return response


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id
        context_token = set_request_id(request_id)
        started = time.perf_counter()
        try:
            response = await call_next(request)
            record_request(
                request.method,
                request.scope.get("route").path if request.scope.get("route") else request.url.path,
                response.status_code,
                time.perf_counter() - started,
            )
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            reset_request_id(context_token)


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path
        method = request.method.upper()
        if settings.APP_ENV.lower() in {"test", "testing"} or not path.startswith(settings.API_V1_PREFIX) or path in {
            f"{settings.API_V1_PREFIX}/health",
            f"{settings.API_V1_PREFIX}/ready",
        }:
            return await call_next(request)

        limit, window, scope = settings.RATE_LIMIT_GENERAL, settings.RATE_LIMIT_WINDOW_SECONDS, "general"
        if path.endswith("/auth/login") and method == "POST":
            limit, scope = settings.RATE_LIMIT_LOGIN, "login"
        elif path.endswith("/auth/register") and method == "POST":
            limit, scope = settings.RATE_LIMIT_REGISTER, "register"
        elif path.endswith("/auth/refresh") and method == "POST":
            limit, scope = settings.RATE_LIMIT_REFRESH, "refresh"
        elif path.endswith("/execute") and method == "POST":
            limit, scope = settings.RATE_LIMIT_EXECUTION, "execution"

        identity = _identity(request)
        try:
            allowed, remaining, retry_after = await check_rate_limit(
                get_redis(), key=f"{scope}:{identity}", limit=limit, window_seconds=window
            )
        except Exception:
            if not settings.RATE_LIMIT_FAIL_OPEN:
                return Response(status_code=503, content="Rate limiter unavailable.")
            return await call_next(request)

        if not allowed:
            return Response(
                status_code=429,
                content="Rate limit exceeded.",
                headers={"Retry-After": str(retry_after), "X-RateLimit-Limit": str(limit), "X-RateLimit-Remaining": "0"},
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        return response


class AuditLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        path = request.url.path
        method = request.method.upper()
        should_audit = path.startswith(settings.API_V1_PREFIX) and (
            method in {"POST", "PUT", "PATCH", "DELETE"}
            or path.endswith("/history")
            or path.endswith("/search")
            or "documentation" in path
        )
        if not should_audit:
            return response

        user_id = getattr(request.state, "audit_user_id", None)
        authorization = request.headers.get("authorization", "")
        if authorization.lower().startswith("bearer "):
            with suppress(TokenError, KeyError, ValueError):
                payload = decode_access_token(authorization[7:].strip())
                user_id = user_id or uuid.UUID(str(payload["sub"]))

        resource_type, resource_id = _resource_info(request)
        workspace_id = _workspace_id(request)
        metadata = {
            "request_id": getattr(request.state, "request_id", None),
            "query": redact_url(str(request.url)) if request.url.query else None,
        }
        async with AsyncSessionLocal() as session:
            session.add(
                AuditLog(
                    user_id=user_id,
                    workspace_id=workspace_id,
                    action=f"HTTP_{method}",
                    method=method,
                    path=path,
                    status_code=response.status_code,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    ip_address=_client_ip(request),
                    user_agent=request.headers.get("user-agent"),
                    metadata_json=metadata,
                )
            )
            try:
                await session.commit()
            except Exception as e:
                logger.warning("Failed to commit audit log: %s", e)
        return response
