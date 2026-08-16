import asyncio
import uuid
import pytest
from httpx import AsyncClient

from app.services.documentation import (
    DocumentationRuleError,
    _operation_url,
    _parameter_list,
    _security_auth,
    import_openapi,
)

@pytest.fixture(autouse=True)
async def cleanup_connections():
    from app.core.database import engine
    await engine.dispose()
    yield
    await engine.dispose()

@pytest.mark.anyio
async def test_openapi_operation_url_uses_server():
    assert _operation_url("/users", [{"url": "https://api.example.com/v1"}]) == "https://api.example.com/v1/users"


@pytest.mark.anyio
async def test_openapi_parameter_conversion():
    headers, query = _parameter_list(
        {"parameters": [{"name": "limit", "in": "query", "example": 10}]},
        {"parameters": [{"name": "X-Trace", "in": "header", "example": "abc"}]},
    )
    assert query == [{"key": "limit", "value": "10", "enabled": True}]
    assert headers == [{"key": "X-Trace", "value": "abc", "enabled": True}]


@pytest.mark.anyio
async def test_openapi_security_detection():
    assert _security_auth({"security": [{"bearerAuth": []}]}, None) == "bearer"
    assert _security_auth({"security": [{"basicAuth": []}]}, None) == "basic"
    assert _security_auth({"security": []}, None) == "none"


@pytest.mark.anyio
async def test_openapi_import_rejects_non_openapi_document():
    class DummySession:
        pass

    with pytest.raises(DocumentationRuleError, match="OpenAPI"):
        await import_openapi(
            DummySession(),
            workspace_id=uuid.uuid4(),
            spec={"swagger": "2.0", "paths": {}},
        )

async def register_and_login(
    client: AsyncClient, name: str, email: str
) -> tuple[dict[str, str], uuid.UUID]:
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
async def test_documentation_endpoints(client: AsyncClient):
    # 1. Register & Login
    email_owner = f"owner_{uuid.uuid4().hex[:6]}@example.com"
    headers_owner, user_owner_id = await register_and_login(client, "Owner User", email_owner)

    email_viewer = f"viewer_{uuid.uuid4().hex[:6]}@example.com"
    headers_viewer, user_viewer_id = await register_and_login(client, "Viewer User", email_viewer)

    # 2. Create workspace
    slug = f"ws-{uuid.uuid4().hex[:6]}"
    ws_res = await client.post(
        "/api/v1/workspaces",
        json={"name": "Workspace Doc Test", "slug": slug},
        headers=headers_owner,
    )
    assert ws_res.status_code == 201
    workspace_id = ws_res.json()["id"]

    # 3. Add Viewer to workspace with VIEWER role
    member_res = await client.post(
        f"/api/v1/workspaces/{workspace_id}/invitations",
        json={"email": email_viewer, "role": "VIEWER"},
        headers=headers_owner,
    )
    assert member_res.status_code == 201
    token_str = member_res.headers["X-Debug-Invitation-Token"]

    accept_res = await client.post(
        f"/api/v1/invitations/{token_str}/accept",
        headers=headers_viewer,
    )
    assert accept_res.status_code == 200

    # 4. Create collection & requests (owner)
    coll_res = await client.post(
        f"/api/v1/workspaces/{workspace_id}/collections",
        json={"name": "Test Collection", "description": "Collection for Doc testing"},
        headers=headers_owner,
    )
    assert coll_res.status_code == 201
    collection_id = coll_res.json()["id"]

    req_res = await client.post(
        f"/api/v1/collections/{collection_id}/requests",
        json={
            "name": "Test Request",
            "method": "POST",
            "url": "https://api.example.com/api/v1/test",
            "headers": [{"key": "X-Test-Header", "value": "test-value", "enabled": True}, {"key": "Authorization", "value": "Bearer my-secret-token", "enabled": True}],
            "query_params": [{"key": "q", "value": "search-query", "enabled": True}],
            "body": '{"key": "value", "password": "supersecretpassword"}',
            "auth_config": {"type": "bearer", "token": "sensitivebearer"},
        },
        headers=headers_owner,
    )
    assert req_res.status_code == 201

    # 5. Fetch documentation summary (viewer should be able to fetch)
    summary_res = await client.get(
        f"/api/v1/workspaces/{workspace_id}/documentation/summary",
        headers=headers_viewer,
    )
    assert summary_res.status_code == 200
    summary_data = summary_res.json()
    assert summary_data["title"] == "Workspace Doc Test"
    assert summary_data["collection_count"] == 1
    assert summary_data["request_count"] == 1

    # 6. Export OpenAPI JSON (owner)
    export_res = await client.get(
        f"/api/v1/workspaces/{workspace_id}/documentation/openapi.json",
        headers=headers_owner,
    )
    assert export_res.status_code == 200
    openapi_spec = export_res.json()
    assert openapi_spec["openapi"] == "3.0.3"
    assert openapi_spec["info"]["title"] == "Workspace Doc Test"
    assert "/api/v1/test" in openapi_spec["paths"]
    
    # Check that credentials are redacted or removed
    operation = openapi_spec["paths"]["/api/v1/test"]["post"]
    # Sensitive header `Authorization` must be redacted/removed
    header_names = [p["name"] for p in operation["parameters"] if p["in"] == "header"]
    assert "Authorization" not in header_names
    assert "X-Test-Header" in header_names

    # Request body: password key in example should be redacted
    body_example = operation["requestBody"]["content"]["application/json"]["example"]
    assert body_example["password"] == "<redacted>"
    assert body_example["key"] == "value"

    # 7. Import OpenAPI document
    # Create new workspace
    new_slug = f"ws-{uuid.uuid4().hex[:6]}"
    new_ws_res = await client.post(
        "/api/v1/workspaces",
        json={"name": "Workspace Import Test", "slug": new_slug},
        headers=headers_owner,
    )
    new_workspace_id = new_ws_res.json()["id"]

    # Try import as Viewer (should fail with 403)
    viewer_inv = await client.post(
        f"/api/v1/workspaces/{new_workspace_id}/invitations",
        json={"email": email_viewer, "role": "VIEWER"},
        headers=headers_owner,
    )
    assert viewer_inv.status_code == 201
    accept_res2 = await client.post(
        f"/api/v1/invitations/{viewer_inv.headers['X-Debug-Invitation-Token']}/accept",
        headers=headers_viewer,
    )
    assert accept_res2.status_code == 200

    import_payload = {
        "collection_name": "Imported Test API",
        "spec": {
            "openapi": "3.0.0",
            "info": {"title": "Imported API Spec", "version": "1.2.3"},
            "paths": {
                "/pets": {
                    "get": {
                        "summary": "List pets",
                        "operationId": "listPets",
                        "tags": ["pets"],
                        "parameters": [
                            {"name": "limit", "in": "query", "required": False, "schema": {"type": "integer"}, "example": 20}
                        ],
                        "responses": {
                            "200": {"description": "OK"}
                        }
                    }
                }
            }
        }
    }
    
    import_fail = await client.post(
        f"/api/v1/workspaces/{new_workspace_id}/documentation/import",
        json=import_payload,
        headers=headers_viewer,
    )
    assert import_fail.status_code == 403

    # Import as Owner (should succeed)
    import_success = await client.post(
        f"/api/v1/workspaces/{new_workspace_id}/documentation/import",
        json=import_payload,
        headers=headers_owner,
    )
    assert import_success.status_code == 201
    import_data = import_success.json()
    assert import_data["collection_name"] == "Imported Test API"
    assert import_data["folder_count"] == 1
    assert import_data["request_count"] == 1

    # Verify requests/folders/collections were created in DB
    collections_res = await client.get(
        f"/api/v1/workspaces/{new_workspace_id}/collections",
        headers=headers_owner,
    )
    assert collections_res.status_code == 200
    collections = collections_res.json()
    assert len(collections) == 1
    assert collections[0]["name"] == "Imported Test API"
