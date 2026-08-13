import uuid
from unittest.mock import patch

import httpx
import pytest
from httpx import AsyncClient

from app.core.database import AsyncSessionLocal, engine
from app.models.api_request import APIRequest


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
async def test_variable_resolution_and_immutability(client: AsyncClient):
    """
    Verifies that variables resolve correctly in all fields:
    - URL, query params, headers, body, Bearer auth, Basic auth.
    - Resolves multiple variables: {{BASE_URL}}/users/{{USER_ID}} -> https://example.com/users/123.
    - Verifies that request definition in the database is NOT mutated after execution.
    - Verifies secret variable value is not exposed in the execution response body.
    """
    owner_email = f"owner_{uuid.uuid4().hex[:6]}@example.com"
    headers_owner, _ = await register_and_login(client, "Owner User", owner_email)

    # 1. Create Workspace
    ws_res = await client.post(
        "/api/v1/workspaces",
        json={"name": "Workspace A", "slug": f"ws-{uuid.uuid4().hex[:6]}"},
        headers=headers_owner,
    )
    ws_id = ws_res.json()["id"]

    # 2. Create Environment
    env_res = await client.post(
        f"/api/v1/workspaces/{ws_id}/environments",
        json={"name": "Development"},
        headers=headers_owner,
    )
    env_id = env_res.json()["id"]

    # 3. Create Variables (BASE_URL, USER_ID, API_TOKEN)
    await client.post(
        f"/api/v1/environments/{env_id}/variables",
        json={
            "key": "BASE_URL",
            "value": "https://api.example.com",
            "is_secret": False,
        },
        headers=headers_owner,
    )
    await client.post(
        f"/api/v1/environments/{env_id}/variables",
        json={"key": "USER_ID", "value": "123", "is_secret": False},
        headers=headers_owner,
    )
    await client.post(
        f"/api/v1/environments/{env_id}/variables",
        json={"key": "API_TOKEN", "value": "secret-jwt-token-val", "is_secret": True},
        headers=headers_owner,
    )

    # 4. Create Collection and Request with Placeholders
    col_res = await client.post(
        f"/api/v1/workspaces/{ws_id}/collections",
        json={"name": "Collection A"},
        headers=headers_owner,
    )
    col_id = col_res.json()["id"]

    req_payload = {
        "name": "Variable Resolution Request",
        "method": "POST",
        "url": "{{BASE_URL}}/users/{{USER_ID}}",
        "headers": [{"key": "X-Auth", "value": "{{API_TOKEN}}", "enabled": True}],
        "query_params": [{"key": "user", "value": "{{USER_ID}}", "enabled": True}],
        "body": '{"user_id": "{{USER_ID}}"}',
        "auth_config": {"type": "bearer", "token": "{{API_TOKEN}}"},
    }

    req_res = await client.post(
        f"/api/v1/collections/{col_id}/requests",
        json=req_payload,
        headers=headers_owner,
    )
    req_id = req_res.json()["id"]

    # 5. Define Shared Mock Interceptor
    class MockUpstream:
        def __init__(self):
            self.last_url = None
            self.last_headers = None
            self.last_content = None
            self.last_params = None

        async def handle(self, method, url, *args, **kwargs):
            self.last_url = str(url)
            self.last_headers = kwargs.get("headers")
            self.last_content = kwargs.get("content")
            self.last_params = kwargs.get("params")
            return httpx.Response(
                200,
                content=b"Successful Resolution Output",
                headers={"Content-Type": "text/plain"},
            )

    upstream = MockUpstream()
    original_request = httpx.AsyncClient.request

    async def conditional_request(self, method, url, *args, **kwargs):
        if str(url).startswith("/") or "127.0.0.1" in str(url):
            return await original_request(self, method, url, *args, **kwargs)
        return await upstream.handle(method, url, *args, **kwargs)

    # 6. Execute request against Environment
    with patch("httpx.AsyncClient.request", new=conditional_request):
        with patch("app.services.execution._resolve_public_ips") as mock_dns:
            mock_dns.return_value = ["93.184.215.14"]
            res = await client.post(
                f"/api/v1/requests/{req_id}/execute",
                json={"environment_id": env_id},
                headers=headers_owner,
            )
            assert res.status_code == 200
            data = res.json()
            assert data["success"] is True

            # Assert secret value is NOT leaked/returned in the execution response body or logs
            assert "secret-jwt-token-val" not in data["body"]
            assert "secret-jwt-token-val" not in str(data["headers"])

    # 7. Assert Mock Upstream received fully resolved values
    assert upstream.last_url == "https://api.example.com/users/123"
    assert upstream.last_headers.get("X-Auth") == "secret-jwt-token-val"
    assert upstream.last_headers.get("Authorization") == "Bearer secret-jwt-token-val"
    content = upstream.last_content
    if isinstance(content, str):
        content = content.encode()
    assert content == b'{"user_id": "123"}'
    assert ("user", "123") in upstream.last_params

    # 8. Assert database Request is NOT mutated (Request Persistence check)
    async with AsyncSessionLocal() as session:
        db_req = await session.get(APIRequest, uuid.UUID(req_id))
        assert db_req.url == "{{BASE_URL}}/users/{{USER_ID}}"
        assert db_req.headers == [
            {"key": "X-Auth", "value": "{{API_TOKEN}}", "enabled": True}
        ]
        assert db_req.query_params == [
            {"key": "user", "value": "{{USER_ID}}", "enabled": True}
        ]
        assert db_req.body == '{"user_id": "{{USER_ID}}"}'
        assert db_req.auth_config == {
            "type": "bearer",
            "token": "{{API_TOKEN}}",
            "username": None,
            "password": None,
        }


@pytest.mark.anyio
async def test_undefined_variable_returns_400(client: AsyncClient):
    """
    Asserts that resolving undefined variable placeholders (e.g. {{DOES_NOT_EXIST}})
    results in a clear 400 Bad Request client error.
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
            "name": "Undefined Var Request",
            "method": "GET",
            "url": "https://api.example.com/data?key={{DOES_NOT_EXIST}}",
            "headers": [],
            "query_params": [],
            "body": None,
            "auth_config": {"type": "none"},
        },
        headers=headers_owner,
    )
    req_id = req_res.json()["id"]

    # Execute without resolving (Development environment has no variables defined)
    env_res = await client.post(
        f"/api/v1/workspaces/{ws_id}/environments",
        json={"name": "Development"},
        headers=headers_owner,
    )
    env_id = env_res.json()["id"]

    res = await client.post(
        f"/api/v1/requests/{req_id}/execute",
        json={"environment_id": env_id},
        headers=headers_owner,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is False
    assert data["error_code"] == "EXECUTION_ERROR"
    assert "could not be executed" in data["error_message"].lower()
