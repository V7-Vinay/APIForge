import pytest
import uuid
from httpx import AsyncClient

@pytest.mark.anyio
async def test_phase4_integration_workflow(client: AsyncClient):
    # 1. Register and login User A
    user_a_email = f"user_a_{uuid.uuid4().hex[:6]}@example.com"
    reg_a = await client.post(
        "/api/v1/auth/register",
        json={"name": "User A", "email": user_a_email, "password": "Password123!"}
    )
    assert reg_a.status_code == 201
    
    login_a = await client.post(
        "/api/v1/auth/login",
        json={"email": user_a_email, "password": "Password123!"}
    )
    assert login_a.status_code == 200
    token_a = login_a.json()["access_token"]
    headers_a = {"Authorization": f"Bearer {token_a}"}

    # 2. Create workspace under User A
    ws_res = await client.post(
        "/api/v1/workspaces",
        json={"name": "WS A", "slug": f"ws-a-{uuid.uuid4().hex[:6]}"},
        headers=headers_a
    )
    assert ws_res.status_code == 201
    workspace_id = ws_res.json()["id"]

    # 3. Create collection under Workspace A
    col_res = await client.post(
        f"/api/v1/workspaces/{workspace_id}/collections",
        json={"name": "Col A", "description": "Collection description"},
        headers=headers_a
    )
    assert col_res.status_code == 201
    collection_id = col_res.json()["id"]

    # 4. Create root folder in Collection A
    fold_res = await client.post(
        f"/api/v1/collections/{collection_id}/folders",
        json={"name": "Folder Root", "parent_id": None},
        headers=headers_a
    )
    assert fold_res.status_code == 201
    root_folder_id = fold_res.json()["id"]

    # Create nested folder under root folder
    nested_res = await client.post(
        f"/api/v1/collections/{collection_id}/folders",
        json={"name": "Folder Nested", "parent_id": root_folder_id},
        headers=headers_a
    )
    assert nested_res.status_code == 201
    nested_folder_id = nested_res.json()["id"]

    # 5. Create request inside Collection A / Nested Folder
    req_res = await client.post(
        f"/api/v1/collections/{collection_id}/requests",
        json={
            "name": "Get Users Request",
            "method": "GET",
            "url": "https://httpbin.org/get",
            "headers": [{"key": "Accept", "value": "application/json"}],
            "query_params": [],
            "body": None,
            "auth_config": {"type": "none"},
            "folder_id": nested_folder_id
        },
        headers=headers_a
    )
    assert req_res.status_code == 201
    request_id = req_res.json()["id"]

    # 6. Update the request
    up_res = await client.patch(
        f"/api/v1/requests/{request_id}",
        json={
            "name": "Updated Request Name",
            "url": "https://httpbin.org/get?updated=true"
        },
        headers=headers_a
    )
    assert up_res.status_code == 200
    assert up_res.json()["name"] == "Updated Request Name"

    # 7. List the collection's requests
    list_res = await client.get(
        f"/api/v1/collections/{collection_id}/requests",
        headers=headers_a
    )
    assert list_res.status_code == 200
    assert len(list_res.json()) >= 1
    assert list_res.json()[0]["id"] == request_id

    # 8. Verify a VIEWER cannot mutate resources
    # Register user B
    user_b_email = f"user_b_{uuid.uuid4().hex[:6]}@example.com"
    reg_b = await client.post(
        "/api/v1/auth/register",
        json={"name": "User B", "email": user_b_email, "password": "Password123!"}
    )
    assert reg_b.status_code == 201
    login_b = await client.post(
        "/api/v1/auth/login",
        json={"email": user_b_email, "password": "Password123!"}
    )
    assert login_b.status_code == 200
    token_b = login_b.json()["access_token"]
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # Invite User B to Workspace A as a VIEWER
    invite_res = await client.post(
        f"/api/v1/workspaces/{workspace_id}/invitations",
        json={"email": user_b_email, "role": "VIEWER"},
        headers=headers_a
    )
    assert invite_res.status_code == 201
    invitation_token = invite_res.headers.get("X-Debug-Invitation-Token")
    assert invitation_token is not None

    # Accept invitation as User B
    accept_res = await client.post(
        f"/api/v1/invitations/{invitation_token}/accept",
        headers=headers_b
    )
    assert accept_res.status_code == 200

    # Verify User B (VIEWER) can GET resources but NOT modify them
    get_col_b = await client.get(
        f"/api/v1/collections/{collection_id}",
        headers=headers_b
    )
    assert get_col_b.status_code == 200 # Allowed to view

    update_col_b = await client.patch(
        f"/api/v1/collections/{collection_id}",
        json={"name": "No Permission Update"},
        headers=headers_b
    )
    assert update_col_b.status_code == 403 # VIEWER role cannot edit collections

    # 9. Verify a non-member cannot access resources by UUID
    user_c_email = f"user_c_{uuid.uuid4().hex[:6]}@example.com"
    await client.post(
        "/api/v1/auth/register",
        json={"name": "User C", "email": user_c_email, "password": "Password123!"}
    )
    login_c = await client.post(
        "/api/v1/auth/login",
        json={"email": user_c_email, "password": "Password123!"}
    )
    token_c = login_c.json()["access_token"]
    headers_c = {"Authorization": f"Bearer {token_c}"}

    get_col_c = await client.get(
        f"/api/v1/collections/{collection_id}",
        headers=headers_c
    )
    assert get_col_c.status_code == 404 # Non-member gets 404 (isolation/leak prevention)

    # 10. Verify a folder from another collection cannot be attached to a request
    # Create Collection B in workspace
    col_b_res = await client.post(
        f"/api/v1/workspaces/{workspace_id}/collections",
        json={"name": "Col B"},
        headers=headers_a
    )
    assert col_b_res.status_code == 201
    collection_b_id = col_b_res.json()["id"]

    # Create folder in Collection B
    fold_b_res = await client.post(
        f"/api/v1/collections/{collection_b_id}/folders",
        json={"name": "Folder in Col B"},
        headers=headers_a
    )
    assert fold_b_res.status_code == 201
    folder_b_id = fold_b_res.json()["id"]

    # Attempt to update Request A (in Collection A) to point to Folder B (in Collection B)
    wrong_folder_update = await client.patch(
        f"/api/v1/requests/{request_id}",
        json={"folder_id": folder_b_id},
        headers=headers_a
    )
    assert wrong_folder_update.status_code == 400
    assert "belong to this collection" in wrong_folder_update.json()["detail"]
