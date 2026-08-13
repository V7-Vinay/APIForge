import uuid
from unittest.mock import patch

import httpx
import pytest
from httpx import AsyncClient

from app.core.database import AsyncSessionLocal, engine
from app.core.config import settings


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
async def test_execution_timeout_error(client: AsyncClient):
    """
    Asserts timeout controls: simulating slow upstream response causes the app
    to return a controlled UPSTREAM_TIMEOUT error instead of a hang.
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
            "name": "Slow request",
            "method": "GET",
            "url": "https://api.example.com/slow",
            "headers": [],
            "query_params": [],
            "body": None,
            "auth_config": {"type": "none"},
        },
        headers=headers_owner,
    )
    req_id = req_res.json()["id"]

    original_request = httpx.AsyncClient.request

    async def conditional_request(self, method, url, *args, **kwargs):
        if str(url).startswith("/") or "127.0.0.1" in str(url):
            return await original_request(self, method, url, *args, **kwargs)
        raise httpx.TimeoutException("Upstream connection timed out")

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
            assert data["success"] is False
            assert data["error_code"] == "UPSTREAM_TIMEOUT"
            assert "timed out" in data["error_message"].lower()


@pytest.mark.anyio
async def test_execution_max_response_size_limit(client: AsyncClient):
    """
    Asserts payload size limits:
    - Responses exceeding settings.EXECUTION_MAX_RESPONSE_SIZE_BYTES return RESPONSE_TOO_LARGE.
    - Verifies that reading terminates early and does not buffer the entire payload into memory.
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
            "name": "Oversized request",
            "method": "GET",
            "url": "https://api.example.com/oversized",
            "headers": [],
            "query_params": [],
            "body": None,
            "auth_config": {"type": "none"},
        },
        headers=headers_owner,
    )
    req_id = req_res.json()["id"]

    # Limit response size configuration temporarily to 50KB for testing
    limit_test_val = 50000

    # We create a mock generator that yields 100 chunks of 10KB each (1MB total).
    # If the engine works correctly, it should abort reading after 6 chunks (60KB),
    # meaning the generator is NOT exhausted.
    chunks_yielded = 0

    async def mock_aiter_bytes(*args, **kwargs):
        nonlocal chunks_yielded
        for _ in range(100):
            chunks_yielded += 1
            yield b"a" * 10000

    mock_resp = httpx.Response(
        200,
        headers={"Content-Type": "text/plain"},
    )
    mock_resp.aiter_bytes = mock_aiter_bytes

    original_request = httpx.AsyncClient.request

    async def conditional_request(self, method, url, *args, **kwargs):
        if str(url).startswith("/") or "127.0.0.1" in str(url):
            return await original_request(self, method, url, *args, **kwargs)
        return mock_resp

    with patch("httpx.AsyncClient.request", new=conditional_request):
        with patch("app.services.execution._resolve_public_ips") as mock_dns:
            mock_dns.return_value = ["93.184.215.14"]

            with patch.object(
                settings, "EXECUTION_MAX_RESPONSE_SIZE_BYTES", new=limit_test_val
            ):
                res = await client.post(
                    f"/api/v1/requests/{req_id}/execute",
                    json={"environment_id": None},
                    headers=headers_owner,
                )
                assert res.status_code == 200
                data = res.json()
                assert data["success"] is False
                assert data["error_code"] == "RESPONSE_TOO_LARGE"
                assert (
                    "exceeded the configured size limit"
                    in data["error_message"].lower()
                )

                # Verify reading terminated early:
                # 6 chunks of 10KB resolves to 60KB, which exceeds 50KB limit.
                # So chunks_yielded must be exactly 6, proving that we did NOT read the remaining 94 chunks (1MB).
                assert chunks_yielded == 6
                assert chunks_yielded < 10
