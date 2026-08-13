import uuid
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.database import AsyncSessionLocal, engine
from app.models.environment import Environment, EnvironmentVariable


@pytest.fixture(autouse=True)
async def cleanup_connections():
    """Dispose the engine connections to prevent event loop mismatch across tests."""
    await engine.dispose()
    yield
    await engine.dispose()


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
async def test_01_execute_request_happy_path(client: AsyncClient):
    """
    Verifies that POST /api/v1/requests/{id}/execute executes successfully
    and resolves request fields using the environment.
    """
    # Register Owner and Workspace A
    email = f"user_{uuid.uuid4().hex[:6]}@example.com"
    headers, _ = await register_and_login(client, "Owner User", email)

    ws_res = await client.post(
        "/api/v1/workspaces",
        json={"name": "Workspace A", "slug": f"ws-{uuid.uuid4().hex[:6]}"},
        headers=headers,
    )
    ws_id = ws_res.json()["id"]

    # Create Collection and Request
    col_res = await client.post(
        f"/api/v1/workspaces/{ws_id}/collections",
        json={"name": "Collection A"},
        headers=headers,
    )
    col_id = col_res.json()["id"]

    req_res = await client.post(
        f"/api/v1/collections/{col_id}/requests",
        json={
            "name": "Execute test",
            "method": "POST",
            "url": "https://api.example.com/users",
            "headers": [{"key": "X-Custom", "value": "test-val", "enabled": True}],
            "query_params": [],
            "body": '{"hello": "world"}',
            "auth_config": {"type": "none"},
        },
        headers=headers,
    )
    req_id = req_res.json()["id"]

    # Mock outbound HTTP request and DNS lookup
    mock_resp = httpx.Response(
        status_code=200,
        content=b'{"message": "Hello from mock upstream"}',
        headers={"Content-Type": "application/json", "Set-Cookie": "secret_cookie"},
    )
    
    original_request = httpx.AsyncClient.request

    async def conditional_request(self, method, url, *args, **kwargs):
        url_str = str(url)
        # If it is relative path or pointing to the local ASGI test app, run original
        if url_str.startswith("/") or "localhost" in url_str or "127.0.0.1" in url_str:
            return await original_request(self, method, url, *args, **kwargs)
        # Otherwise, return mock response for outbound targets
        return mock_resp

    with patch("httpx.AsyncClient.request", new=conditional_request):
        with patch("app.services.execution._resolve_public_ips") as mock_dns:
            mock_dns.return_value = ["93.184.215.14"]
            
            exec_res = await client.post(
                f"/api/v1/requests/{req_id}/execute",
                json={"environment_id": None},
                headers=headers,
            )
            assert exec_res.status_code == 200
            data = exec_res.json()
            assert data["success"] is True
            assert data["status_code"] == 200
            assert "Hello from mock upstream" in data["body"]
            # Verify sensitive response headers are redacted
            assert data["headers"]["set-cookie"] == "[REDACTED]"
            assert data["duration_ms"] > 0


@pytest.mark.anyio
async def test_02_execute_request_ssrf_blocking(client: AsyncClient):
    """
    Verifies that calling execution against blocked IPs (e.g. localhost) returns success=False and SSRF_BLOCKED.
    """
    email = f"user_{uuid.uuid4().hex[:6]}@example.com"
    headers, _ = await register_and_login(client, "Owner User", email)

    ws_res = await client.post(
        "/api/v1/workspaces",
        json={"name": "Workspace A", "slug": f"ws-{uuid.uuid4().hex[:6]}"},
        headers=headers,
    )
    ws_id = ws_res.json()["id"]

    col_res = await client.post(
        f"/api/v1/workspaces/{ws_id}/collections",
        json={"name": "Collection A"},
        headers=headers,
    )
    col_id = col_res.json()["id"]

    req_res = await client.post(
        f"/api/v1/collections/{col_id}/requests",
        json={
            "name": "SSRF test",
            "method": "GET",
            "url": "http://127.0.0.1/admin/secrets",
            "headers": [],
            "query_params": [],
            "body": None,
            "auth_config": {"type": "none"},
        },
        headers=headers,
    )
    req_id = req_res.json()["id"]

    exec_res = await client.post(
        f"/api/v1/requests/{req_id}/execute",
        json={"environment_id": None},
        headers=headers,
    )
    assert exec_res.status_code == 200
    data = exec_res.json()
    assert data["success"] is False
    assert data["error_code"] == "SSRF_BLOCKED"
    assert "private or local network addresses" in data["error_message"]


@pytest.mark.anyio
async def test_03_execute_request_rbac_viewer(client: AsyncClient):
    """
    Verifies that a user with VIEWER role in Workspace A cannot execute requests.
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
            "name": "Execute test",
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

    # Register and invite Viewer
    viewer_email = f"viewer_{uuid.uuid4().hex[:6]}@example.com"
    headers_viewer, _ = await register_and_login(client, "Viewer User", viewer_email)

    invite_res = await client.post(
        f"/api/v1/workspaces/{ws_id}/invitations",
        json={"email": viewer_email, "role": "VIEWER"},
        headers=headers_owner,
    )
    assert invite_res.status_code == 201
    invitation_token = invite_res.headers.get("X-Debug-Invitation-Token")

    accept_res = await client.post(
        f"/api/v1/invitations/{invitation_token}/accept",
        headers=headers_viewer,
    )
    assert accept_res.status_code == 200

    # Act: execute request as VIEWER
    exec_res = await client.post(
        f"/api/v1/requests/{req_id}/execute",
        json={"environment_id": None},
        headers=headers_viewer,
    )
    # Assert: returns 403 Forbidden
    assert exec_res.status_code == 403
