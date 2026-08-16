"""Phase 11 service-level integration tests requiring PostgreSQL/Redis."""

import uuid

import pytest
from httpx import AsyncClient

pytestmark = [pytest.mark.integration, pytest.mark.security]


async def _register_login(client: AsyncClient, name: str) -> dict[str, str]:
    email = f"{name.lower().replace(' ', '_')}_{uuid.uuid4().hex[:8]}@example.com"
    password = "Password123!"
    response = await client.post(
        "/api/v1/auth/register",
        json={"name": name, "email": email, "password": password},
    )
    assert response.status_code == 201
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.mark.anyio
async def test_authenticated_workspace_resource_flow_and_tenant_isolation(client: AsyncClient):
    owner = await _register_login(client, "Phase11Owner")
    outsider = await _register_login(client, "Phase11Outsider")

    workspace = await client.post(
        "/api/v1/workspaces",
        json={"name": "Phase11 Workspace", "slug": f"phase11-{uuid.uuid4().hex[:8]}"},
        headers=owner,
    )
    assert workspace.status_code == 201
    workspace_id = workspace.json()["id"]

    collection = await client.post(
        f"/api/v1/workspaces/{workspace_id}/collections",
        json={"name": "Secure Collection"},
        headers=owner,
    )
    assert collection.status_code == 201
    collection_id = collection.json()["id"]

    outsider_read = await client.get(
        f"/api/v1/collections/{collection_id}", headers=outsider
    )
    assert outsider_read.status_code == 404

    outsider_search = await client.get(
        f"/api/v1/workspaces/{workspace_id}/search?q=Secure", headers=outsider
    )
    assert outsider_search.status_code == 404


@pytest.mark.anyio
async def test_request_auth_credentials_are_not_returned(client: AsyncClient):
    owner = await _register_login(client, "Phase11Secrets")

    workspace = await client.post(
        "/api/v1/workspaces",
        json={"name": "Secret Workspace", "slug": f"secret-{uuid.uuid4().hex[:8]}"},
        headers=owner,
    )
    assert workspace.status_code == 201
    workspace_id = workspace.json()["id"]

    collection = await client.post(
        f"/api/v1/workspaces/{workspace_id}/collections",
        json={"name": "Secret Collection"},
        headers=owner,
    )
    assert collection.status_code == 201
    collection_id = collection.json()["id"]

    created = await client.post(
        f"/api/v1/collections/{collection_id}/requests",
        json={
            "name": "Credentialed Request",
            "method": "GET",
            "url": "https://example.com",
            "auth_config": {
                "type": "bearer",
                "token": "DO-NOT-EXPOSE-THIS-TOKEN",
            },
        },
        headers=owner,
    )
    assert created.status_code == 201
    request_id = created.json()["id"]

    fetched = await client.get(f"/api/v1/requests/{request_id}", headers=owner)
    assert fetched.status_code == 200
    body = fetched.text
    assert "DO-NOT-EXPOSE-THIS-TOKEN" not in body
    assert "password" not in body.lower()


@pytest.mark.anyio
async def test_audit_logs_are_admin_only(client: AsyncClient):
    owner = await _register_login(client, "Phase11AuditOwner")
    workspace = await client.post(
        "/api/v1/workspaces",
        json={"name": "Audit Workspace", "slug": f"audit-{uuid.uuid4().hex[:8]}"},
        headers=owner,
    )
    assert workspace.status_code == 201
    workspace_id = workspace.json()["id"]

    logs = await client.get(f"/api/v1/workspaces/{workspace_id}/audit-logs", headers=owner)
    assert logs.status_code == 200
    assert isinstance(logs.json(), list)


@pytest.mark.anyio
async def test_health_and_readiness_contracts(client: AsyncClient):
    health = await client.get("/api/v1/health")
    assert health.status_code == 200
    payload = health.json()
    assert payload["status"] == "ok"
    assert payload["service"] == "apiforge-backend"
    assert "version" in payload
