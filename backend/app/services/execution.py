import asyncio
import ipaddress
import socket
import time
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.api_request import APIRequest
from app.models.environment import Environment
from app.models.execution_history import ExecutionHistory
from app.services.environments import resolve_variables


class ExecutionRuleError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400):
        self.code = code
        self.status_code = status_code
        super().__init__(message)


@dataclass(frozen=True)
class ResolvedRequest:
    method: str
    url: str
    headers: dict[str, str]
    params: list[tuple[str, str]]
    body: str | None


_BLOCKED_NETWORKS = (
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("100.64.0.0/10"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.0.0.0/24"),
    ipaddress.ip_network("192.0.2.0/24"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("198.18.0.0/15"),
    ipaddress.ip_network("198.51.100.0/24"),
    ipaddress.ip_network("203.0.113.0/24"),
    ipaddress.ip_network("224.0.0.0/4"),
    ipaddress.ip_network("240.0.0.0/4"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
    ipaddress.ip_network("ff00::/8"),
)


async def _resolve_public_ips(hostname: str) -> list[str]:
    try:
        infos = await asyncio.to_thread(
            socket.getaddrinfo,
            hostname,
            None,
            type=socket.SOCK_STREAM,
        )
    except socket.gaierror as exc:
        raise ExecutionRuleError(
            "UPSTREAM_DNS_ERROR", "The target hostname could not be resolved.", 502
        ) from exc

    ips = sorted({info[4][0] for info in infos})
    if not ips:
        raise ExecutionRuleError(
            "UPSTREAM_DNS_ERROR", "The target hostname has no usable address.", 502
        )

    for raw_ip in ips:
        try:
            address = ipaddress.ip_address(raw_ip)
        except ValueError as exc:
            raise ExecutionRuleError(
                "UPSTREAM_DNS_ERROR", "The target resolved to an invalid address.", 502
            ) from exc
        if (
            address.is_private
            or address.is_loopback
            or address.is_link_local
            or address.is_reserved
            or address.is_multicast
        ):
            raise ExecutionRuleError(
                "SSRF_BLOCKED",
                "Requests to private or local network addresses are blocked.",
                403,
            )
        if any(address in network for network in _BLOCKED_NETWORKS):
            raise ExecutionRuleError(
                "SSRF_BLOCKED",
                "Requests to restricted network addresses are blocked.",
                403,
            )
    return ips


def _validate_url(url: str) -> str:
    value = url.strip()
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"}:
        raise ExecutionRuleError(
            "UNSUPPORTED_PROTOCOL", "Only http:// and https:// URLs are supported.", 400
        )
    if not parsed.hostname:
        raise ExecutionRuleError(
            "INVALID_REQUEST_URL", "The request URL must contain a hostname.", 400
        )
    if parsed.username or parsed.password:
        raise ExecutionRuleError(
            "INVALID_REQUEST_URL", "Credentials in request URLs are not supported.", 400
        )
    return value


def _header_map(items: list | None) -> dict[str, str]:
    result: dict[str, str] = {}
    for item in items or []:
        if not isinstance(item, dict) or not item.get("enabled", True):
            continue
        key = str(item.get("key", "")).strip()
        value = str(item.get("value", ""))
        if key:
            result[key] = value
    return result


def _params(items: list | None) -> list[tuple[str, str]]:
    result: list[tuple[str, str]] = []
    for item in items or []:
        if not isinstance(item, dict) or not item.get("enabled", True):
            continue
        key = str(item.get("key", "")).strip()
        if key:
            result.append((key, str(item.get("value", ""))))
    return result


def _apply_auth(headers: dict[str, str], auth_config: dict | None) -> None:
    auth = auth_config or {"type": "none"}
    auth_type = auth.get("type", "none")
    if auth_type == "none":
        return
    if auth_type == "bearer":
        token = auth.get("token")
        if not token:
            raise ExecutionRuleError(
                "INVALID_AUTH_CONFIG", "Bearer authentication requires a token."
            )
        headers["Authorization"] = f"Bearer {token}"
        return
    if auth_type == "basic":
        username = auth.get("username")
        password = auth.get("password")
        if username is None or password is None:
            raise ExecutionRuleError(
                "INVALID_AUTH_CONFIG",
                "Basic authentication requires username and password.",
            )
        import base64

        encoded = base64.b64encode(f"{username}:{password}".encode()).decode()
        headers["Authorization"] = f"Basic {encoded}"
        return
    raise ExecutionRuleError(
        "INVALID_AUTH_CONFIG", "Unsupported authentication configuration."
    )


async def resolve_request(
    session: AsyncSession, *, request: APIRequest, environment: Environment | None
) -> ResolvedRequest:
    async def resolve(value: str) -> str:
        if environment is None:
            return value
        return await resolve_variables(
            session, environment_id=environment.id, text=value, reveal_secrets=True
        )

    url = _validate_url(await resolve(request.url))
    headers = {
        await resolve(k): await resolve(v)
        for k, v in _header_map(request.headers).items()
    }
    params = [
        (await resolve(k), await resolve(v)) for k, v in _params(request.query_params)
    ]
    body = await resolve(request.body) if request.body is not None else None
    auth_config = request.auth_config or {"type": "none"}
    if environment is not None:
        # Resolve only string fields; preserve the typed auth structure.
        auth_config = {
            key: await resolve(value) if isinstance(value, str) else value
            for key, value in auth_config.items()
        }
    _apply_auth(headers, auth_config)
    return ResolvedRequest(
        method=request.method, url=url, headers=headers, params=params, body=body
    )


def _redact_headers(headers: dict[str, str]) -> dict[str, str]:
    sensitive = {
        "authorization",
        "proxy-authorization",
        "cookie",
        "set-cookie",
        "x-api-key",
        "x-auth-token",
    }
    return {
        key: "[REDACTED]" if key.lower() in sensitive else value
        for key, value in headers.items()
    }


async def _read_response(response: httpx.Response) -> tuple[str | None, str, int, bool]:
    max_bytes = settings.EXECUTION_MAX_RESPONSE_SIZE_BYTES
    chunks: list[bytes] = []
    total = 0
    async for chunk in response.aiter_bytes():
        total += len(chunk)
        if total > max_bytes:
            raise ExecutionRuleError(
                "RESPONSE_TOO_LARGE",
                "The upstream response exceeded the configured size limit.",
                413,
            )
        chunks.append(chunk)
    data = b"".join(chunks)
    content_type = response.headers.get("content-type", "").split(";", 1)[0].lower()
    is_text = (
        content_type.startswith("text/")
        or content_type.endswith("+json")
        or content_type.endswith("+xml")
        or content_type
        in {
            "application/json",
            "application/xml",
            "application/javascript",
            "application/graphql",
        }
    )
    if not is_text:
        return None, content_type or "application/octet-stream", total, False
    charset = response.encoding or "utf-8"
    return (
        data.decode(charset, errors="replace"),
        content_type or "text/plain",
        total,
        True,
    )


import re
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode

def redact_sensitive_text(text: str | None) -> str | None:
    if text is None:
        return None
    # 1. Bearer token pattern
    text = re.sub(r'(?i)\bbearer\s+[a-zA-Z0-9_\-\.\~/\+=]+', 'Bearer [REDACTED]', text)
    # 2. Basic credentials pattern
    text = re.sub(r'(?i)\bbasic\s+[a-zA-Z0-9_\-\.\~/\+=]+', 'Basic [REDACTED]', text)
    # 3. JSON / quoted key-value pattern (matches "token": "..." or 'password': "...", etc.)
    text = re.sub(
        r'(?i)(["\'](?:password|token|secret|api_key|apikey|pwd|pass|credential|authorization|cookie|x-api-key|set-cookie)["\']\s*:\s*)(["\'])(?:.*?)(["\'])',
        r'\1\2[REDACTED]\3',
        text
    )
    # 4. Form-urlencoded / Query params in text (matches token=abc or password=xyz)
    text = re.sub(
        r'(?i)(\b(?:password|token|secret|api_key|apikey|pwd|pass|credential|authorization|cookie|x-api-key|set-cookie)\b\s*=\s*)([^&\s"\']+)',
        r'\1[REDACTED]',
        text
    )
    return text

def redact_url(url: str) -> str:
    try:
        parsed = urlparse(url)
        if not parsed.query:
            return url
        q_params = []
        sensitive_keys = {
            "password", "token", "secret", "api_key", "apikey", "pwd", "pass",
            "credential", "authorization", "cookie", "set-cookie", "x-api-key"
        }
        for k, v in parse_qsl(parsed.query, keep_blank_values=True):
            if k.lower() in sensitive_keys or any(sk in k.lower() for sk in ["token", "secret", "key", "pass"]):
                q_params.append((k, "[REDACTED]"))
            else:
                q_params.append((k, v))
        new_query = urlencode(q_params)
        return urlunparse(parsed._replace(query=new_query))
    except Exception:
        return redact_sensitive_text(url) or url

def redact_headers_dict(headers: dict[str, str]) -> dict[str, str]:
    sensitive_keys = {
        "authorization", "proxy-authorization", "cookie", "set-cookie",
        "x-api-key", "x-auth-token", "api-key"
    }
    redacted = {}
    for k, v in headers.items():
        if k.lower() in sensitive_keys:
            redacted[k] = "[REDACTED]"
        else:
            redacted[k] = redact_sensitive_text(v) or v
    return redacted

def sanitize_execution_data(
    url: str,
    headers: dict,
    body: str | None,
    error_message: str | None
) -> tuple[str, dict, str | None, str | None]:
    return (
        redact_url(url),
        redact_headers_dict(headers),
        redact_sensitive_text(body),
        redact_sensitive_text(error_message)
    )


async def record_execution_history(
    session: AsyncSession,
    *,
    request: APIRequest,
    workspace_id,
    user_id,
    environment: Environment | None,
    result: dict,
) -> None:
    raw_url = result.get("url", request.url)
    raw_headers = result.get("headers", {})
    raw_body = result.get("body")
    raw_error = result.get("error_message")

    redacted_url, redacted_headers, redacted_body, redacted_error = sanitize_execution_data(
        raw_url, raw_headers, raw_body, raw_error
    )

    history = ExecutionHistory(
        request_id=request.id,
        workspace_id=workspace_id,
        user_id=user_id,
        environment_id=environment.id if environment else None,
        method=result.get("method", request.method),
        url=redacted_url,
        status_code=result.get("status_code"),
        success=result.get("success", False),
        duration_ms=result.get("duration_ms"),
        response_size_bytes=result.get("response_size_bytes", 0),
        response_headers=redacted_headers,
        response_body=redacted_body,
        content_type=result.get("content_type"),
        error_code=result.get("error_code"),
        error_message=redacted_error,
    )
    session.add(history)
    await session.commit()


async def execute_request(
    session: AsyncSession,
    *,
    request: APIRequest,
    environment: Environment | None,
    workspace_id=None,
    user_id=None,
) -> dict:
    resolved = await resolve_request(session, request=request, environment=environment)
    current_url = _validate_url(resolved.url)
    redirects = 0
    started = time.perf_counter()

    timeout = httpx.Timeout(
        settings.EXECUTION_TIMEOUT_SECONDS,
        connect=settings.EXECUTION_CONNECT_TIMEOUT_SECONDS,
    )

    async with httpx.AsyncClient(
        timeout=timeout, follow_redirects=False, trust_env=False
    ) as client:
        while True:
            parsed = urlparse(current_url)
            await _resolve_public_ips(parsed.hostname or "")
            try:
                response = await client.request(
                    resolved.method,
                    current_url,
                    headers=resolved.headers,
                    params=resolved.params,
                    content=resolved.body,
                )
            except httpx.TimeoutException as exc:
                raise ExecutionRuleError(
                    "UPSTREAM_TIMEOUT", "The upstream request timed out.", 504
                ) from exc
            except httpx.ConnectError as exc:
                raise ExecutionRuleError(
                    "UPSTREAM_CONNECTION_ERROR",
                    "The upstream server could not be reached.",
                    502,
                ) from exc
            except httpx.RequestError as exc:
                raise ExecutionRuleError(
                    "UPSTREAM_REQUEST_ERROR",
                    "The upstream request could not be completed.",
                    502,
                ) from exc

            if response.status_code in {
                301,
                302,
                303,
                307,
                308,
            } and response.headers.get("location"):
                if redirects >= settings.EXECUTION_MAX_REDIRECTS:
                    raise ExecutionRuleError(
                        "REDIRECT_LIMIT_EXCEEDED",
                        "The upstream redirect limit was exceeded.",
                        502,
                    )
                current_url = _validate_url(
                    urljoin(current_url, response.headers["location"])
                )
                redirects += 1
                continue
            break

        body, content_type, response_size, is_text = await _read_response(response)

    duration_ms = round((time.perf_counter() - started) * 1000, 2)
    result = {
        "success": True,
        "method": resolved.method,
        "url": current_url,
        "status_code": response.status_code,
        "headers": _redact_headers(dict(response.headers)),
        "body": body,
        "content_type": content_type,
        "response_size_bytes": response_size,
        "body_is_text": is_text,
        "duration_ms": duration_ms,
        "redirects": redirects,
        "error_code": None,
        "error_message": None,
    }
    if workspace_id is not None and user_id is not None:
        await record_execution_history(
            session,
            request=request,
            workspace_id=workspace_id,
            user_id=user_id,
            environment=environment,
            result=result,
        )
    return result
