import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.database import AsyncSessionLocal, engine
from app.models.workspace import WorkspaceRole
from app.models.execution_history import ExecutionHistory

@pytest.fixture(autouse=True)
async def cleanup_connections():
    await engine.dispose()
    yield
    await engine.dispose()

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
async def test_history_authorization_and_rbac(client: AsyncClient):
    owner_email = f"owner_{uuid.uuid4().hex[:6]}@example.com"
    headers_owner, owner_id = await register_and_login(client, "Owner User", owner_email)

    ws_res = await client.post(
        "/api/v1/workspaces",
        json={"name": "WS", "slug": f"ws-{uuid.uuid4().hex[:6]}"},
        headers=headers_owner,
    )
    ws_id = ws_res.json()["id"]

    col_res = await client.post(
        f"/api/v1/workspaces/{ws_id}/collections",
        json={"name": "Col"},
        headers=headers_owner,
    )
    col_id = col_res.json()["id"]

    req_res = await client.post(
        f"/api/v1/collections/{col_id}/requests",
        json={
            "name": "Req",
            "method": "GET",
            "url": "https://httpbin.org/get",
            "headers": [],
            "query_params": [],
            "body": None,
            "auth_config": {"type": "none"},
        },
        headers=headers_owner,
    )
    req_id = req_res.json()["id"]

    viewer_email = f"viewer_{uuid.uuid4().hex[:6]}@example.com"
    headers_viewer, viewer_id = await register_and_login(client, "Viewer User", viewer_email)

    invite_res = await client.post(
        f"/api/v1/workspaces/{ws_id}/invitations",
        json={"email": viewer_email, "role": "VIEWER"},
        headers=headers_owner,
    )
    invitation_token = invite_res.headers.get("X-Debug-Invitation-Token")
    await client.post(
        f"/api/v1/invitations/{invitation_token}/accept",
        headers=headers_viewer,
    )

    hist_viewer = await client.get(
        f"/api/v1/requests/{req_id}/history",
        headers=headers_viewer,
    )
    assert hist_viewer.status_code == 200

    exec_viewer = await client.post(
        f"/api/v1/requests/{req_id}/execute",
        json={},
        headers=headers_viewer,
    )
    assert exec_viewer.status_code == 403

    hist_owner = await client.get(
        f"/api/v1/requests/{req_id}/history",
        headers=headers_owner,
    )
    assert hist_owner.status_code == 200


@pytest.mark.anyio
async def test_secrets_masking_in_request_response(client: AsyncClient):
    owner_email = f"owner_{uuid.uuid4().hex[:6]}@example.com"
    headers_owner, _ = await register_and_login(client, "Owner User", owner_email)

    ws_res = await client.post(
        "/api/v1/workspaces",
        json={"name": "WS", "slug": f"ws-{uuid.uuid4().hex[:6]}"},
        headers=headers_owner,
    )
    ws_id = ws_res.json()["id"]

    col_res = await client.post(
        f"/api/v1/workspaces/{ws_id}/collections",
        json={"name": "Col"},
        headers=headers_owner,
    )
    col_id = col_res.json()["id"]

    req_res = await client.post(
        f"/api/v1/collections/{col_id}/requests",
        json={
            "name": "Req Secret",
            "method": "POST",
            "url": "https://httpbin.org/post",
            "headers": [],
            "query_params": [],
            "body": None,
            "auth_config": {
                "type": "basic",
                "username": "my-user",
                "password": "secret-password"
            },
        },
        headers=headers_owner,
    )
    assert req_res.status_code == 201
    
    body = req_res.json()
    assert "secret-password" not in str(body)
    assert "password" not in body["auth_config"]
    assert body["auth_config"]["has_credentials"] is True
    assert body["auth_config"]["username"] == "my-user"

    get_res = await client.get(
        f"/api/v1/requests/{body['id']}",
        headers=headers_owner,
    )
    assert get_res.status_code == 200
    assert "secret-password" not in str(get_res.json())


@pytest.mark.anyio
async def test_execution_history_redaction_direct_db(client: AsyncClient):
    owner_email = f"owner_{uuid.uuid4().hex[:6]}@example.com"
    headers_owner, _ = await register_and_login(client, "Owner User", owner_email)

    ws_res = await client.post(
        "/api/v1/workspaces",
        json={"name": "WS", "slug": f"ws-{uuid.uuid4().hex[:6]}"},
        headers=headers_owner,
    )
    ws_id = ws_res.json()["id"]

    col_res = await client.post(
        f"/api/v1/workspaces/{ws_id}/collections",
        json={"name": "Col"},
        headers=headers_owner,
    )
    col_id = col_res.json()["id"]

    req_res = await client.post(
        f"/api/v1/collections/{col_id}/requests",
        json={
            "name": "Req Redaction",
            "method": "GET",
            "url": "https://httpbin.org/get?secret_token=my-secret-val&other=normal",
            "headers": [
                {"key": "Authorization", "value": "Bearer my-secret-token", "enabled": True},
                {"key": "Cookie", "value": "session=secret-session", "enabled": True}
            ],
            "query_params": [],
            "body": None,
            "auth_config": {"type": "none"},
        },
        headers=headers_owner,
    )
    req_id = req_res.json()["id"]

    await client.post(
        f"/api/v1/requests/{req_id}/execute",
        json={},
        headers=headers_owner,
    )
    
    async with AsyncSessionLocal() as db:
        histories = await db.scalars(
            select(ExecutionHistory).where(ExecutionHistory.request_id == req_id)
        )
        history_list = list(histories)
        assert len(history_list) >= 1
        history = history_list[0]
        
        from urllib.parse import unquote
        decoded_url = unquote(history.url)
        assert "my-secret-val" not in decoded_url
        assert "secret_token=[REDACTED]" in decoded_url
        assert "other=normal" in decoded_url


@pytest.mark.anyio
async def test_tenant_isolation_cross_workspace_environment(client: AsyncClient):
    owner_email = f"owner_{uuid.uuid4().hex[:6]}@example.com"
    headers_owner, _ = await register_and_login(client, "Owner User", owner_email)

    ws_res_a = await client.post(
        "/api/v1/workspaces",
        json={"name": "WS A", "slug": f"ws-{uuid.uuid4().hex[:6]}"},
        headers=headers_owner,
    )
    ws_id_a = ws_res_a.json()["id"]

    col_res_a = await client.post(
        f"/api/v1/workspaces/{ws_id_a}/collections",
        json={"name": "Col A"},
        headers=headers_owner,
    )
    col_id_a = col_res_a.json()["id"]

    req_res_a = await client.post(
        f"/api/v1/collections/{col_id_a}/requests",
        json={
            "name": "Req A",
            "method": "GET",
            "url": "https://httpbin.org/get",
            "headers": [],
            "query_params": [],
            "body": None,
            "auth_config": {"type": "none"},
        },
        headers=headers_owner,
    )
    req_id_a = req_res_a.json()["id"]

    ws_res_b = await client.post(
        "/api/v1/workspaces",
        json={"name": "WS B", "slug": f"ws-{uuid.uuid4().hex[:6]}"},
        headers=headers_owner,
    )
    ws_id_b = ws_res_b.json()["id"]

    env_res_b = await client.post(
        f"/api/v1/workspaces/{ws_id_b}/environments",
        json={"name": "Env B"},
        headers=headers_owner,
    )
    env_id_b = env_res_b.json()["id"]

    exec_res = await client.post(
        f"/api/v1/requests/{req_id_a}/execute",
        json={"environment_id": env_id_b},
        headers=headers_owner,
    )
    assert exec_res.status_code == 403
    assert "does not belong to the request workspace" in exec_res.json()["error"]["message"]


@pytest.mark.anyio
async def test_rbac_environment_mutations_and_workspace_patch(client: AsyncClient):
    owner_email = f"owner_{uuid.uuid4().hex[:6]}@example.com"
    headers_owner, _ = await register_and_login(client, "Owner User", owner_email)

    ws_res = await client.post(
        "/api/v1/workspaces",
        json={"name": "WS", "slug": f"ws-{uuid.uuid4().hex[:6]}"},
        headers=headers_owner,
    )
    ws_id = ws_res.json()["id"]

    editor_email = f"editor_{uuid.uuid4().hex[:6]}@example.com"
    headers_editor, _ = await register_and_login(client, "Editor User", editor_email)

    invite_res = await client.post(
        f"/api/v1/workspaces/{ws_id}/invitations",
        json={"email": editor_email, "role": "EDITOR"},
        headers=headers_owner,
    )
    invitation_token = invite_res.headers.get("X-Debug-Invitation-Token")
    await client.post(
        f"/api/v1/invitations/{invitation_token}/accept",
        headers=headers_editor,
    )

    create_env_res = await client.post(
        f"/api/v1/workspaces/{ws_id}/environments",
        json={"name": "Editor Env"},
        headers=headers_editor,
    )
    assert create_env_res.status_code == 403

    owner_env_res = await client.post(
        f"/api/v1/workspaces/{ws_id}/environments",
        json={"name": "Owner Env"},
        headers=headers_owner,
    )
    assert owner_env_res.status_code == 201

    patch_editor_res = await client.patch(
        f"/api/v1/workspaces/{ws_id}",
        json={"name": "New WS Name Editor"},
        headers=headers_editor,
    )
    assert patch_editor_res.status_code == 403

    patch_owner_res = await client.patch(
        f"/api/v1/workspaces/{ws_id}",
        json={"name": "New WS Name Owner"},
        headers=headers_owner,
    )
    assert patch_owner_res.status_code == 200
    assert patch_owner_res.json()["name"] == "New WS Name Owner"
