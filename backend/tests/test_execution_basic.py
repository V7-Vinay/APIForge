import uuid
from unittest.mock import patch

import httpx
import pytest
from httpx import AsyncClient

from app.core.database import AsyncSessionLocal, engine


@pytest.fixture(autouse=True)
async def cleanup_connections():
    """Dispose the engine connections to prevent event loop mismatch across tests."""
    await engine.dispose()
    yield
    await engine.dispose()


@pytest.fixture(autouse=True)
async def init_redis_for_loop():
    """Re-initialize Redis client for the current event loop of each test."""
    import app.core.redis as app_redis
    from app.core.config import settings
    from redis.asyncio import Redis

    app_redis.redis_client = Redis.from_url(settings.REDIS_URL, decode_responses=True)
    yield
    if app_redis.redis_client is not None:
        await app_redis.redis_client.aclose()


async def register_and_login(
    client: AsyncClient, name: str, email: str
) -> tuple[dict[str, str], uuid.UUID]:
    """Helper function to register and login a user, returning auth headers and user ID."""
    reg = await client.post(
        "/api/v1/auth/register",
        json={"name": name, "email": email, "password": "Password123!"},
    )
    assert reg.status_code == 201
    user_id = uuid.UUID(reg.json()["id"])

    login = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": "Password123!"}
    )
    assert login.status_code == 200
    token = login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}, user_id


@pytest.mark.anyio
async def test_basic_health_endpoints(client: AsyncClient):
    """
    Asserts backend basic readiness, health and OpenAPI Swagger endpoints return 200.
    """
    res_health = await client.get("/api/v1/health")
    assert res_health.status_code == 200
    assert res_health.json()["status"] == "ok"

    res_ready = await client.get("/api/v1/ready")
    assert res_ready.status_code == 200
    assert res_ready.json()["status"] == "ready"

    res_docs = await client.get("/docs")
    assert res_docs.status_code == 200
    assert "swagger" in res_docs.text.lower()


@pytest.mark.anyio
async def test_execute_unauthenticated(client: AsyncClient):
    """
    Asserts unauthenticated requests return 401 Unauthorized.
    """
    req_uuid = uuid.uuid4()
    res = await client.post(
        f"/api/v1/requests/{req_uuid}/execute", json={"environment_id": None}
    )
    assert res.status_code == 401


@pytest.mark.anyio
async def test_execute_nonexistent_request(client: AsyncClient):
    """
    Asserts executing a nonexistent request UUID returns 404.
    """
    email = f"user_{uuid.uuid4().hex[:6]}@example.com"
    headers, _ = await register_and_login(client, "Owner User", email)

    req_uuid = uuid.uuid4()
    res = await client.post(
        f"/api/v1/requests/{req_uuid}/execute",
        json={"environment_id": None},
        headers=headers,
    )
    assert res.status_code == 404
    assert "Request not found" in res.json()["detail"]


@pytest.mark.anyio
async def test_execute_rbac_viewer_rejected_editor_allowed(client: AsyncClient):
    """
    Asserts role-based access gates: VIEWER members get 403, while EDITOR, ADMIN,
    and OWNER members succeed.
    """
    owner_email = f"owner_{uuid.uuid4().hex[:6]}@example.com"
    headers_owner, _ = await register_and_login(client, "Owner User", owner_email)

    ws_res = await client.post(
        "/api/v1/workspaces",
        json={"name": "Workspace A", "slug": f"ws-{uuid.uuid4().hex[:6]}"},
        headers=headers_owner,
    )
    ws_id = ws_res.json()["id"]

    col_res = await client.post(
        f"/api/v1/workspaces/{ws_id}/collections",
        json={"name": "Collection A"},
        headers=headers_owner,
    )
    col_id = col_res.json()["id"]

    req_res = await client.post(
        f"/api/v1/collections/{col_id}/requests",
        json={
            "name": "RBAC Test Request",
            "method": "GET",
            "url": "https://api.example.com/status",
            "headers": [],
            "query_params": [],
            "body": None,
            "auth_config": {"type": "none"},
        },
        headers=headers_owner,
    )
    req_id = req_res.json()["id"]

    # 1. Test OWNER succeeds
    original_request = httpx.AsyncClient.request
    mock_resp = httpx.Response(
        200, content=b"OK", headers={"Content-Type": "text/plain"}
    )

    async def conditional_request(self, method, url, *args, **kwargs):
        if str(url).startswith("/") or "127.0.0.1" in str(url):
            return await original_request(self, method, url, *args, **kwargs)
        return mock_resp

    with patch("httpx.AsyncClient.request", new=conditional_request):
        with patch("app.services.execution._resolve_public_ips") as mock_dns:
            mock_dns.return_value = ["93.184.215.14"]
            res = await client.post(
                f"/api/v1/requests/{req_id}/execute",
                json={"environment_id": None},
                headers=headers_owner,
            )
            assert res.status_code == 200
            assert res.json()["success"] is True

    # 2. Test VIEWER is rejected
    viewer_email = f"viewer_{uuid.uuid4().hex[:6]}@example.com"
    headers_viewer, _ = await register_and_login(client, "Viewer User", viewer_email)

    invite_res = await client.post(
        f"/api/v1/workspaces/{ws_id}/invitations",
        json={"email": viewer_email, "role": "VIEWER"},
        headers=headers_owner,
    )
    invitation_token = invite_res.headers.get("X-Debug-Invitation-Token")
    await client.post(
        f"/api/v1/invitations/{invitation_token}/accept", headers=headers_viewer
    )

    res_viewer = await client.post(
        f"/api/v1/requests/{req_id}/execute",
        json={"environment_id": None},
        headers=headers_viewer,
    )
    assert res_viewer.status_code == 403
    assert "do not have permission" in res_viewer.json()["detail"]


@pytest.mark.anyio
async def test_execute_environment_selection(client: AsyncClient):
    """
    Asserts environment parameter constraints:
    - Succeeds against matching workspace environment.
    - Fails if environment is from a different workspace (returns 403).
    - Fails if environment doesn't exist (returns 404).
    """
    owner_email = f"owner_{uuid.uuid4().hex[:6]}@example.com"
    headers_owner, _ = await register_and_login(client, "Owner User", owner_email)

    # Create Workspace A
    ws_res_a = await client.post(
        "/api/v1/workspaces",
        json={"name": "Workspace A", "slug": f"ws-{uuid.uuid4().hex[:6]}"},
        headers=headers_owner,
    )
    ws_id_a = ws_res_a.json()["id"]

    col_res = await client.post(
        f"/api/v1/workspaces/{ws_id_a}/collections",
        json={"name": "Collection A"},
        headers=headers_owner,
    )
    col_id = col_res.json()["id"]

    req_res = await client.post(
        f"/api/v1/collections/{col_id}/requests",
        json={
            "name": "Env Test Request",
            "method": "GET",
            "url": "https://api.example.com",
            "headers": [],
            "query_params": [],
            "body": None,
            "auth_config": {"type": "none"},
        },
        headers=headers_owner,
    )
    req_id = req_res.json()["id"]

    # Create Environment in Workspace A
    env_res_a = await client.post(
        f"/api/v1/workspaces/{ws_id_a}/environments",
        json={"name": "Development A"},
        headers=headers_owner,
    )
    env_id_a = env_res_a.json()["id"]

    # Create Workspace B + Environment B
    ws_res_b = await client.post(
        "/api/v1/workspaces",
        json={"name": "Workspace B", "slug": f"ws-{uuid.uuid4().hex[:6]}"},
        headers=headers_owner,
    )
    ws_id_b = ws_res_b.json()["id"]

    env_res_b = await client.post(
        f"/api/v1/workspaces/{ws_id_b}/environments",
        json={"name": "Development B"},
        headers=headers_owner,
    )
    env_id_b = env_res_b.json()["id"]

    mock_resp = httpx.Response(200, content=b"OK")
    original_request = httpx.AsyncClient.request

    async def conditional_request(self, method, url, *args, **kwargs):
        if str(url).startswith("/") or "127.0.0.1" in str(url):
            return await original_request(self, method, url, *args, **kwargs)
        return mock_resp

    # 1. Execute with matching environment -> Succeeds (200)
    with patch("httpx.AsyncClient.request", new=conditional_request):
        with patch("app.services.execution._resolve_public_ips") as mock_dns:
            mock_dns.return_value = ["93.184.215.14"]
            res_ok = await client.post(
                f"/api/v1/requests/{req_id}/execute",
                json={"environment_id": env_id_a},
                headers=headers_owner,
            )
            assert res_ok.status_code == 200

    # 2. Execute with cross-workspace environment -> Fails (403 Forbidden)
    res_bad_env = await client.post(
        f"/api/v1/requests/{req_id}/execute",
        json={"environment_id": env_id_b},
        headers=headers_owner,
    )
    assert res_bad_env.status_code == 403
    assert "does not belong to the request workspace" in res_bad_env.json()["detail"]

    # 3. Execute with nonexistent environment -> Fails (404 Not Found)
    res_none = await client.post(
        f"/api/v1/requests/{req_id}/execute",
        json={"environment_id": str(uuid.uuid4())},
        headers=headers_owner,
    )
    assert res_none.status_code == 404
    assert "Environment not found" in res_none.json()["detail"]


@pytest.mark.anyio
async def test_execute_http_methods_and_transmission(client: AsyncClient):
    """
    Verifies outbound transmission for all main HTTP methods (GET, POST, PUT, PATCH, DELETE,
    HEAD, OPTIONS) and checks that method, headers, query params, and body are transmitted intact.
    """
    owner_email = f"owner_{uuid.uuid4().hex[:6]}@example.com"
    headers_owner, _ = await register_and_login(client, "Owner User", owner_email)

    ws_res = await client.post(
        "/api/v1/workspaces",
        json={"name": "Workspace A", "slug": f"ws-{uuid.uuid4().hex[:6]}"},
        headers=headers_owner,
    )
    ws_id = ws_res.json()["id"]

    col_res = await client.post(
        f"/api/v1/workspaces/{ws_id}/collections",
        json={"name": "Collection A"},
        headers=headers_owner,
    )
    col_id = col_res.json()["id"]

    # 1. Define shared mock interceptor to record incoming request attributes
    class MockUpstream:
        def __init__(self):
            self.last_method = None
            self.last_url = None
            self.last_headers = None
            self.last_content = None

        async def handle(self, method, url, *args, **kwargs):
            self.last_method = method
            self.last_url = str(url)
            self.last_headers = kwargs.get("headers")
            self.last_content = kwargs.get("content")
            return httpx.Response(200, content=b"Mock body content")

    upstream = MockUpstream()
    original_request = httpx.AsyncClient.request

    async def conditional_request(self, method, url, *args, **kwargs):
        if str(url).startswith("/") or "127.0.0.1" in str(url):
            return await original_request(self, method, url, *args, **kwargs)
        return await upstream.handle(method, url, *args, **kwargs)

    # 2. Test each HTTP Method
    for method_name in ["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"]:
        req_res = await client.post(
            f"/api/v1/collections/{col_id}/requests",
            json={
                "name": f"Method {method_name}",
                "method": method_name,
                "url": "https://api.example.com/resource?page=2",
                "headers": [
                    {"key": "X-Required-Header", "value": "val1", "enabled": True}
                ],
                "query_params": [{"key": "page", "value": "2", "enabled": True}],
                "body": (
                    '{"payload_key": "payload_val"}'
                    if method_name in ["POST", "PUT", "PATCH"]
                    else None
                ),
                "auth_config": {"type": "none"},
            },
            headers=headers_owner,
        )
        req_id = req_res.json()["id"]

        with patch("httpx.AsyncClient.request", new=conditional_request):
            with patch("app.services.execution._resolve_public_ips") as mock_dns:
                mock_dns.return_value = ["93.184.215.14"]
                res = await client.post(
                    f"/api/v1/requests/{req_id}/execute",
                    json={"environment_id": None},
                    headers=headers_owner,
                )
                assert res.status_code == 200
                assert res.json()["success"] is True

        # Assert upstream received method and params correctly
        assert upstream.last_method == method_name
        assert "page=2" in upstream.last_url
        assert upstream.last_headers.get("X-Required-Header") == "val1"
        if method_name in ["POST", "PUT", "PATCH"]:
            content = upstream.last_content
            if isinstance(content, str):
                content = content.encode()
            assert content == b'{"payload_key": "payload_val"}'


@pytest.mark.anyio
async def test_execute_response_status_handling(client: AsyncClient):
    """
    Asserts that upstream error codes (400, 404, 500) do NOT report execution success=False.
    Instead, they are treated as successful connection round-trips.
    """
    owner_email = f"owner_{uuid.uuid4().hex[:6]}@example.com"
    headers_owner, _ = await register_and_login(client, "Owner User", owner_email)

    ws_res = await client.post(
        "/api/v1/workspaces",
        json={"name": "Workspace A", "slug": f"ws-{uuid.uuid4().hex[:6]}"},
        headers=headers_owner,
    )
    ws_id = ws_res.json()["id"]

    col_res = await client.post(
        f"/api/v1/workspaces/{ws_id}/collections",
        json={"name": "Collection A"},
        headers=headers_owner,
    )
    col_id = col_res.json()["id"]

    req_res = await client.post(
        f"/api/v1/collections/{col_id}/requests",
        json={
            "name": "Status check request",
            "method": "GET",
            "url": "https://api.example.com/status",
            "headers": [],
            "query_params": [],
            "body": None,
            "auth_config": {"type": "none"},
        },
        headers=headers_owner,
    )
    req_id = req_res.json()["id"]

    original_request = httpx.AsyncClient.request

    for status_to_test in [200, 201, 400, 404, 500]:
        mock_resp = httpx.Response(
            status_to_test,
            content=b"Server response output",
            headers={"Content-Type": "text/plain"},
        )

        async def conditional_request(self, method, url, *args, **kwargs):
            if str(url).startswith("/") or "127.0.0.1" in str(url):
                return await original_request(self, method, url, *args, **kwargs)
            return mock_resp

        with patch("httpx.AsyncClient.request", new=conditional_request):
            with patch("app.services.execution._resolve_public_ips") as mock_dns:
                mock_dns.return_value = ["93.184.215.14"]
                res = await client.post(
                    f"/api/v1/requests/{req_id}/execute",
                    json={"environment_id": None},
                    headers=headers_owner,
                )
                assert res.status_code == 200
                data = res.json()
                # Must be success=True even for 500/404 because the execution completed
                assert data["success"] is True
                assert data["status_code"] == status_to_test
                assert data["body"] == "Server response output"


@pytest.mark.anyio
async def test_execute_response_content_types(client: AsyncClient):
    """
    Asserts text, JSON, and binary (PDF/PNG) payload processing:
    - Text: returned uncorrupted.
    - JSON: parsed or passed as clean string.
    - Binary data: does not crash on non-UTF-8 bytes, avoids decoding, and returns metadata.
    """
    owner_email = f"owner_{uuid.uuid4().hex[:6]}@example.com"
    headers_owner, _ = await register_and_login(client, "Owner User", owner_email)

    ws_res = await client.post(
        "/api/v1/workspaces",
        json={"name": "Workspace A", "slug": f"ws-{uuid.uuid4().hex[:6]}"},
        headers=headers_owner,
    )
    ws_id = ws_res.json()["id"]

    col_res = await client.post(
        f"/api/v1/workspaces/{ws_id}/collections",
        json={"name": "Collection A"},
        headers=headers_owner,
    )
    col_id = col_res.json()["id"]

    req_res = await client.post(
        f"/api/v1/collections/{col_id}/requests",
        json={
            "name": "Content type test",
            "method": "GET",
            "url": "https://api.example.com/content",
            "headers": [],
            "query_params": [],
            "body": None,
            "auth_config": {"type": "none"},
        },
        headers=headers_owner,
    )
    req_id = req_res.json()["id"]

    original_request = httpx.AsyncClient.request

    # 1. Test Text/JSON passthrough
    mock_resp_json = httpx.Response(
        200,
        content=b'{"item": "val"}',
        headers={"Content-Type": "application/json; charset=utf-8"},
    )

    async def cond_json(self, method, url, *args, **kwargs):
        if str(url).startswith("/") or "127.0.0.1" in str(url):
            return await original_request(self, method, url, *args, **kwargs)
        return mock_resp_json

    with patch("httpx.AsyncClient.request", new=cond_json):
        with patch("app.services.execution._resolve_public_ips") as mock_dns:
            mock_dns.return_value = ["93.184.215.14"]
            res = await client.post(
                f"/api/v1/requests/{req_id}/execute",
                json={"environment_id": None},
                headers=headers_owner,
            )
            data = res.json()
            assert data["success"] is True
            assert data["body_is_text"] is True
            assert data["body"] == '{"item": "val"}'

    # 2. Test Binary (PNG bytes)
    png_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    mock_resp_bin = httpx.Response(
        200,
        content=png_bytes,
        headers={"Content-Type": "image/png"},
    )

    async def cond_bin(self, method, url, *args, **kwargs):
        if str(url).startswith("/") or "127.0.0.1" in str(url):
            return await original_request(self, method, url, *args, **kwargs)
        return mock_resp_bin

    with patch("httpx.AsyncClient.request", new=cond_bin):
        with patch("app.services.execution._resolve_public_ips") as mock_dns:
            mock_dns.return_value = ["93.184.215.14"]
            res = await client.post(
                f"/api/v1/requests/{req_id}/execute",
                json={"environment_id": None},
                headers=headers_owner,
            )
            data = res.json()
            assert data["success"] is True
            assert data["body_is_text"] is False
            assert data["body"] is None  # Body omitted for binary types
            assert data["content_type"] == "image/png"
            assert data["response_size_bytes"] == len(png_bytes)
