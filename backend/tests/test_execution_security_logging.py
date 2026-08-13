import logging
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
async def test_execution_logs_and_exceptions_sanitize_secrets(
    client: AsyncClient, caplog
):
    """
    Asserts log sanitization:
    - Capture logs during execution of requests containing Bearer tokens, cookies, Basic auth,
      and secret environment variables.
    - Asserts that none of the raw secrets appear in plaintext in log records or error details.
    """
    # Enable capturing of all logs at DEBUG/INFO level
    caplog.set_level(logging.DEBUG)

    owner_email = f"owner_{uuid.uuid4().hex[:6]}@example.com"
    headers_owner, _ = await register_and_login(client, "Owner User", owner_email)

    ws_res = await client.post(
        "/api/v1/workspaces",
        json={"name": "Workspace A", "slug": f"ws-{uuid.uuid4().hex[:6]}"},
        headers=headers_owner,
    )
    ws_id = ws_res.json()["id"]

    env_res = await client.post(
        f"/api/v1/workspaces/{ws_id}/environments",
        json={"name": "Development"},
        headers=headers_owner,
    )
    env_id = env_res.json()["id"]

    # Variable containing sensitive credential
    secret_val = "highly-confidential-secret-credential-value"
    await client.post(
        f"/api/v1/environments/{env_id}/variables",
        json={"key": "SECRET_TOKEN", "value": secret_val, "is_secret": True},
        headers=headers_owner,
    )

    col_res = await client.post(
        f"/api/v1/workspaces/{ws_id}/collections",
        json={"name": "Collection A"},
        headers=headers_owner,
    )
    col_id = col_res.json()["id"]

    # 1. Create a request with multiple headers and authorization config containing secrets
    req_res = await client.post(
        f"/api/v1/collections/{col_id}/requests",
        json={
            "name": "Secret logging test",
            "method": "POST",
            "url": "https://api.example.com/login",
            "headers": [
                {
                    "key": "Cookie",
                    "value": "session=my-secret-cookie-id",
                    "enabled": True,
                },
                {"key": "X-API-Key", "value": "{{SECRET_TOKEN}}", "enabled": True},
            ],
            "query_params": [],
            "body": '{"auth_secret": "{{SECRET_TOKEN}}"}',
            "auth_config": {
                "type": "basic",
                "username": "admin",
                "password": "{{SECRET_TOKEN}}",
            },
        },
        headers=headers_owner,
    )
    req_id = req_res.json()["id"]

    mock_resp = httpx.Response(
        200,
        content=b'{"authenticated": true}',
        headers={
            "Content-Type": "application/json",
            "Set-Cookie": "res_cookie_secret_123",
        },
    )
    original_request = httpx.AsyncClient.request

    async def conditional_request(self, method, url, *args, **kwargs):
        if str(url).startswith("/") or "127.0.0.1" in str(url):
            return await original_request(self, method, url, *args, **kwargs)
        return mock_resp

    # 2. Execute and capture logs
    with patch("httpx.AsyncClient.request", new=conditional_request):
        with patch("app.services.execution._resolve_public_ips") as mock_dns:
            mock_dns.return_value = ["93.184.215.14"]
            res = await client.post(
                f"/api/v1/requests/{req_id}/execute",
                json={"environment_id": env_id},
                headers=headers_owner,
            )
            assert res.status_code == 200

    # 3. Assert plaintext secrets do NOT appear in logs
    log_text = caplog.text
    assert secret_val not in log_text
    assert "my-secret-cookie-id" not in log_text
    assert "res_cookie_secret_123" not in log_text

    # 4. Trigger an exception to test exception message sanitization.
    # Create request with unsupported scheme that resolves to private credential URL
    req_bad_res = await client.post(
        f"/api/v1/collections/{col_id}/requests",
        json={
            "name": "Exception leak test",
            "method": "GET",
            "url": "ftp://{{SECRET_TOKEN}}@api.example.com",
            "headers": [],
            "query_params": [],
            "body": None,
            "auth_config": {"type": "none"},
        },
        headers=headers_owner,
    )
    req_bad_id = req_bad_res.json()["id"]

    res_err = await client.post(
        f"/api/v1/requests/{req_bad_id}/execute",
        json={"environment_id": env_id},
        headers=headers_owner,
    )
    assert res_err.status_code == 200
    err_data = res_err.json()
    assert err_data["success"] is False
    assert err_data["error_code"] in ["UNSUPPORTED_PROTOCOL", "INVALID_REQUEST_URL"]

    # Assert exception messages and response body do NOT contain the raw secret
    assert secret_val not in err_data["error_message"]
    assert secret_val not in caplog.text
