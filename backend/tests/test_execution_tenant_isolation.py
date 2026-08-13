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
async def test_tenant_isolation_cross_workspace_environment_rejected(
    client: AsyncClient,
):
    """
    Verifies that a request belonging to Workspace A cannot be executed against an environment
    belonging to Workspace B, even when triggered by a user with access to both workspaces.

    Attack Vector:
    An attacker attempts to read variables/secrets from a target environment (Workspace B) by attaching
    it to a request in a workspace they fully control (Workspace A), trying to bypass environment access limits.

    Mitigation:
    The API router validates that the request collection workspace ID matches the environment workspace ID,
    returning a 403 Forbidden when there is a mismatch.
    """
    owner_email = f"owner_{uuid.uuid4().hex[:6]}@example.com"
    headers_owner, _ = await register_and_login(client, "Owner User", owner_email)

    # 1. Create Workspace A + Request A
    ws_res_a = await client.post(
        "/api/v1/workspaces",
        json={"name": "Workspace A", "slug": f"ws-{uuid.uuid4().hex[:6]}"},
        headers=headers_owner,
    )
    ws_id_a = ws_res_a.json()["id"]

    col_res_a = await client.post(
        f"/api/v1/workspaces/{ws_id_a}/collections",
        json={"name": "Collection A"},
        headers=headers_owner,
    )
    col_id_a = col_res_a.json()["id"]

    req_res_a = await client.post(
        f"/api/v1/collections/{col_id_a}/requests",
        json={
            "name": "Request A",
            "method": "GET",
            "url": "https://api.example.com",
            "headers": [],
            "query_params": [],
            "body": None,
            "auth_config": {"type": "none"},
        },
        headers=headers_owner,
    )
    req_id_a = req_res_a.json()["id"]

    # 2. Create Workspace B + Environment B
    ws_res_b = await client.post(
        "/api/v1/workspaces",
        json={"name": "Workspace B", "slug": f"ws-{uuid.uuid4().hex[:6]}"},
        headers=headers_owner,
    )
    ws_id_b = ws_res_b.json()["id"]

    env_res_b = await client.post(
        f"/api/v1/workspaces/{ws_id_b}/environments",
        json={"name": "Environment B"},
        headers=headers_owner,
    )
    env_id_b = env_res_b.json()["id"]

    # 3. Trigger execution of Request A using Environment B
    res = await client.post(
        f"/api/v1/requests/{req_id_a}/execute",
        json={"environment_id": env_id_b},
        headers=headers_owner,
    )
    assert res.status_code == 403
    assert "does not belong to the request workspace" in res.json()["detail"]


@pytest.mark.anyio
async def test_tenant_isolation_unauthorized_user_blocked(client: AsyncClient):
    """
    Verifies that a user belonging exclusively to Workspace B cannot execute or access
    Workspace A's requests or environments, even if they guess or acquire the direct UUIDs.

    Attack Vector:
    Direct Object Reference (IDOR) / Metadata Leakage. An external attacker guesses/leaks the UUID
    of Workspace A's requests or environments and attempts to execute them or read resolved secrets.

    Mitigation:
    APIForge resolves user memberships and rejects access with a clean 404 Not Found to prevent leaking
    existence of private resources.
    """
    # 1. User A creates Workspace A, Environment A, Request A
    owner_a_email = f"owner_a_{uuid.uuid4().hex[:6]}@example.com"
    headers_a, _ = await register_and_login(client, "User A", owner_a_email)

    ws_res_a = await client.post(
        "/api/v1/workspaces",
        json={"name": "Workspace A", "slug": f"ws-{uuid.uuid4().hex[:6]}"},
        headers=headers_a,
    )
    ws_id_a = ws_res_a.json()["id"]

    env_res_a = await client.post(
        f"/api/v1/workspaces/{ws_id_a}/environments",
        json={"name": "Environment A"},
        headers=headers_a,
    )
    env_id_a = env_res_a.json()["id"]

    col_res_a = await client.post(
        f"/api/v1/workspaces/{ws_id_a}/collections",
        json={"name": "Collection A"},
        headers=headers_a,
    )
    col_id_a = col_res_a.json()["id"]

    req_res_a = await client.post(
        f"/api/v1/collections/{col_id_a}/requests",
        json={
            "name": "Request A",
            "method": "GET",
            "url": "https://api.example.com",
            "headers": [],
            "query_params": [],
            "body": None,
            "auth_config": {"type": "none"},
        },
        headers=headers_a,
    )
    req_id_a = req_res_a.json()["id"]

    # 2. User B registers and creates Workspace B (having no membership in Workspace A)
    owner_b_email = f"owner_b_{uuid.uuid4().hex[:6]}@example.com"
    headers_b, _ = await register_and_login(client, "User B", owner_b_email)

    # 3. User B attempts to execute Request A directly by UUID -> Returns 404 Not Found
    res_req = await client.post(
        f"/api/v1/requests/{req_id_a}/execute",
        json={"environment_id": None},
        headers=headers_b,
    )
    assert res_req.status_code == 404
    assert "Request not found" in res_req.json()["detail"]

    # 4. User B attempts to execute Request A directly using Environment A directly -> Returns 404 Not Found
    res_req_env = await client.post(
        f"/api/v1/requests/{req_id_a}/execute",
        json={"environment_id": env_id_a},
        headers=headers_b,
    )
    assert res_req_env.status_code == 404
