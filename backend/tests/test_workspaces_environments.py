import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.database import AsyncSessionLocal, engine
from app.models.environment import Environment, EnvironmentVariable
from app.services.environments import decrypt_value


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
async def test_01_create_workspace(client: AsyncClient):
    """
    Scenario 1: Create workspace.
    Verifies that POST /api/v1/workspaces creates a workspace and returns the correct response shape.
    """
    email = f"user_{uuid.uuid4().hex[:6]}@example.com"
    headers, user_id = await register_and_login(client, "Owner User", email)

    slug = f"workspace-{uuid.uuid4().hex[:6]}"
    ws_res = await client.post(
        "/api/v1/workspaces",
        json={"name": "Workspace A", "slug": slug},
        headers=headers,
    )
    assert ws_res.status_code == 201
    data = ws_res.json()
    assert "id" in data
    assert data["name"] == "Workspace A"
    assert data["slug"] == slug
    assert uuid.UUID(data["created_by"]) == user_id
    assert "created_at" in data


@pytest.mark.anyio
async def test_02_create_environments(client: AsyncClient):
    """
    Scenario 2: Create environments.
    Verifies Development and Production environments are created under Workspace A.
    """
    email = f"user_{uuid.uuid4().hex[:6]}@example.com"
    headers, _ = await register_and_login(client, "Owner User", email)

    ws_res = await client.post(
        "/api/v1/workspaces",
        json={"name": "Workspace A", "slug": f"ws-{uuid.uuid4().hex[:6]}"},
        headers=headers,
    )
    ws_id = ws_res.json()["id"]

    for env_name in ["Development", "Production"]:
        env_res = await client.post(
            f"/api/v1/workspaces/{ws_id}/environments",
            json={"name": env_name, "description": f"{env_name} env"},
            headers=headers,
        )
        assert env_res.status_code == 201
        data = env_res.json()
        assert data["name"] == env_name
        assert data["workspace_id"] == ws_id


@pytest.mark.anyio
async def test_03_add_variable(client: AsyncClient):
    """
    Scenario 3: Add variable.
    Verifies adding BASE_URL = https://api.example.com to Development as non-secret.
    """
    email = f"user_{uuid.uuid4().hex[:6]}@example.com"
    headers, _ = await register_and_login(client, "Owner User", email)

    ws_res = await client.post(
        "/api/v1/workspaces",
        json={"name": "Workspace A", "slug": f"ws-{uuid.uuid4().hex[:6]}"},
        headers=headers,
    )
    ws_id = ws_res.json()["id"]

    env_res = await client.post(
        f"/api/v1/workspaces/{ws_id}/environments",
        json={"name": "Development"},
        headers=headers,
    )
    env_id = env_res.json()["id"]

    var_res = await client.post(
        f"/api/v1/environments/{env_id}/variables",
        json={
            "key": "BASE_URL",
            "value": "https://api.example.com",
            "is_secret": False,
        },
        headers=headers,
    )
    assert var_res.status_code == 201
    data = var_res.json()
    assert data["key"] == "BASE_URL"
    assert data["is_secret"] is False
    assert "id" in data


@pytest.mark.anyio
async def test_04_add_secret(client: AsyncClient):
    """
    Scenario 4: Add secret.
    Verifies adding API_TOKEN secret variable doesn't expose raw value in normal CRUD responses.
    """
    email = f"user_{uuid.uuid4().hex[:6]}@example.com"
    headers, _ = await register_and_login(client, "Owner User", email)

    ws_res = await client.post(
        "/api/v1/workspaces",
        json={"name": "Workspace A", "slug": f"ws-{uuid.uuid4().hex[:6]}"},
        headers=headers,
    )
    ws_id = ws_res.json()["id"]

    env_res = await client.post(
        f"/api/v1/workspaces/{ws_id}/environments",
        json={"name": "Development"},
        headers=headers,
    )
    env_id = env_res.json()["id"]

    var_res = await client.post(
        f"/api/v1/environments/{env_id}/variables",
        json={"key": "API_TOKEN", "value": "my-secret-token", "is_secret": True},
        headers=headers,
    )
    assert var_res.status_code == 201
    data = var_res.json()
    assert data["key"] == "API_TOKEN"
    assert data["is_secret"] is True
    # The normal VariableResponse schema has no "value" field
    assert "value" not in data


@pytest.mark.anyio
async def test_05_list_variables(client: AsyncClient):
    """
    Scenario 5: List variables.
    Verifies GET /api/v1/environments/{id}/variables lists variables, and that
    normal listings do not leak raw secret values or plaintext values (they follow VariableResponse schema).
    """
    email = f"user_{uuid.uuid4().hex[:6]}@example.com"
    headers, _ = await register_and_login(client, "Owner User", email)

    ws_res = await client.post(
        "/api/v1/workspaces",
        json={"name": "Workspace A", "slug": f"ws-{uuid.uuid4().hex[:6]}"},
        headers=headers,
    )
    ws_id = ws_res.json()["id"]

    env_res = await client.post(
        f"/api/v1/workspaces/{ws_id}/environments",
        json={"name": "Development"},
        headers=headers,
    )
    env_id = env_res.json()["id"]

    await client.post(
        f"/api/v1/environments/{env_id}/variables",
        json={
            "key": "BASE_URL",
            "value": "https://api.example.com",
            "is_secret": False,
        },
        headers=headers,
    )
    await client.post(
        f"/api/v1/environments/{env_id}/variables",
        json={"key": "API_TOKEN", "value": "my-secret-token", "is_secret": True},
        headers=headers,
    )

    list_res = await client.get(
        f"/api/v1/environments/{env_id}/variables", headers=headers
    )
    assert list_res.status_code == 200
    variables = list_res.json()
    assert len(variables) == 2
    for var in variables:
        # Values should be omitted entirely from listings
        assert "value" not in var


@pytest.mark.anyio
async def test_06_test_resolution(client: AsyncClient):
    """
    Scenario 6: Test resolution.
    Verifies POST /resolve resolves non-secret variables correctly.
    """
    email = f"user_{uuid.uuid4().hex[:6]}@example.com"
    headers, _ = await register_and_login(client, "Owner User", email)

    ws_res = await client.post(
        "/api/v1/workspaces",
        json={"name": "Workspace A", "slug": f"ws-{uuid.uuid4().hex[:6]}"},
        headers=headers,
    )
    ws_id = ws_res.json()["id"]

    env_res = await client.post(
        f"/api/v1/workspaces/{ws_id}/environments",
        json={"name": "Development"},
        headers=headers,
    )
    env_id = env_res.json()["id"]

    await client.post(
        f"/api/v1/environments/{env_id}/variables",
        json={
            "key": "BASE_URL",
            "value": "https://api.example.com",
            "is_secret": False,
        },
        headers=headers,
    )

    resolve_res = await client.post(
        f"/api/v1/environments/{env_id}/resolve",
        json={"text": "{{BASE_URL}}/users"},
        headers=headers,
    )
    assert resolve_res.status_code == 200
    assert resolve_res.json()["resolved_text"] == "https://api.example.com/users"


@pytest.mark.anyio
async def test_07_test_secret_masking_on_resolve(client: AsyncClient):
    """
    Scenario 7: Test secret masking on resolve.
    Verifies that the generic resolve endpoint masks secrets (returning '********')
    while the direct reveal endpoint returns the plaintext secret to authorized editors.
    """
    email = f"user_{uuid.uuid4().hex[:6]}@example.com"
    headers, _ = await register_and_login(client, "Owner User", email)

    ws_res = await client.post(
        "/api/v1/workspaces",
        json={"name": "Workspace A", "slug": f"ws-{uuid.uuid4().hex[:6]}"},
        headers=headers,
    )
    ws_id = ws_res.json()["id"]

    env_res = await client.post(
        f"/api/v1/workspaces/{ws_id}/environments",
        json={"name": "Development"},
        headers=headers,
    )
    env_id = env_res.json()["id"]

    var_res = await client.post(
        f"/api/v1/environments/{env_id}/variables",
        json={"key": "API_TOKEN", "value": "my-secret-token", "is_secret": True},
        headers=headers,
    )
    var_id = var_res.json()["id"]

    # Generic resolve should mask secrets
    resolve_res = await client.post(
        f"/api/v1/environments/{env_id}/resolve",
        json={"text": "{{API_TOKEN}}"},
        headers=headers,
    )
    assert resolve_res.status_code == 200
    assert resolve_res.json()["resolved_text"] == "********"

    # Dedicated reveal endpoint reveals the plaintext to authorized editor
    reveal_res = await client.get(
        f"/api/v1/environment-variables/{var_id}/reveal", headers=headers
    )
    assert reveal_res.status_code == 200
    assert reveal_res.json()["value"] == "my-secret-token"


@pytest.mark.anyio
async def test_08_test_undefined_variable(client: AsyncClient):
    """
    Scenario 8: Test undefined variable.
    Verifies that resolving an undefined variable returns a 400 Bad Request error.
    """
    email = f"user_{uuid.uuid4().hex[:6]}@example.com"
    headers, _ = await register_and_login(client, "Owner User", email)

    ws_res = await client.post(
        "/api/v1/workspaces",
        json={"name": "Workspace A", "slug": f"ws-{uuid.uuid4().hex[:6]}"},
        headers=headers,
    )
    ws_id = ws_res.json()["id"]

    env_res = await client.post(
        f"/api/v1/workspaces/{ws_id}/environments",
        json={"name": "Development"},
        headers=headers,
    )
    env_id = env_res.json()["id"]

    resolve_res = await client.post(
        f"/api/v1/environments/{env_id}/resolve",
        json={"text": "{{DOES_NOT_EXIST}}"},
        headers=headers,
    )
    assert resolve_res.status_code == 400
    assert (
        "Undefined environment variables: DOES_NOT_EXIST"
        in resolve_res.json()["detail"]
    )


@pytest.mark.anyio
async def test_09_test_duplicate_variable(client: AsyncClient):
    """
    Scenario 9: Test duplicate variable.
    Verifies that creating a duplicate variable in the same environment returns 409 Conflict.
    """
    email = f"user_{uuid.uuid4().hex[:6]}@example.com"
    headers, _ = await register_and_login(client, "Owner User", email)

    ws_res = await client.post(
        "/api/v1/workspaces",
        json={"name": "Workspace A", "slug": f"ws-{uuid.uuid4().hex[:6]}"},
        headers=headers,
    )
    ws_id = ws_res.json()["id"]

    env_res = await client.post(
        f"/api/v1/workspaces/{ws_id}/environments",
        json={"name": "Development"},
        headers=headers,
    )
    env_id = env_res.json()["id"]

    first_res = await client.post(
        f"/api/v1/environments/{env_id}/variables",
        json={
            "key": "BASE_URL",
            "value": "https://api.example.com",
            "is_secret": False,
        },
        headers=headers,
    )
    assert first_res.status_code == 201

    second_res = await client.post(
        f"/api/v1/environments/{env_id}/variables",
        json={
            "key": "BASE_URL",
            "value": "https://api.duplicate.com",
            "is_secret": False,
        },
        headers=headers,
    )
    assert second_res.status_code == 409


@pytest.mark.anyio
async def test_10_test_rbac_viewer_role(client: AsyncClient):
    """
    Scenario 10: Test RBAC (VIEWER role).
    Verifies that a VIEWER-role member on Workspace A cannot mutate environments/variables (403),
    but can read them (200).
    """
    # 1. Register Owner and create Workspace A + Environment Development
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

    var_res = await client.post(
        f"/api/v1/environments/{env_id}/variables",
        json={
            "key": "BASE_URL",
            "value": "https://api.example.com",
            "is_secret": False,
        },
        headers=headers_owner,
    )
    var_id = var_res.json()["id"]

    # 2. Register Viewer and invite to Workspace A as VIEWER
    viewer_email = f"viewer_{uuid.uuid4().hex[:6]}@example.com"
    headers_viewer, _ = await register_and_login(client, "Viewer User", viewer_email)

    invite_res = await client.post(
        f"/api/v1/workspaces/{ws_id}/invitations",
        json={"email": viewer_email, "role": "VIEWER"},
        headers=headers_owner,
    )
    assert invite_res.status_code == 201
    invitation_token = invite_res.headers.get("X-Debug-Invitation-Token")
    assert invitation_token is not None

    accept_res = await client.post(
        f"/api/v1/invitations/{invitation_token}/accept", headers=headers_viewer
    )
    assert accept_res.status_code == 200

    # 3. Assert VIEWER mutations return 403 Forbidden
    # Create environment
    create_env_bad = await client.post(
        f"/api/v1/workspaces/{ws_id}/environments",
        json={"name": "Bad Env"},
        headers=headers_viewer,
    )
    assert create_env_bad.status_code == 403

    # Update environment
    update_env_bad = await client.patch(
        f"/api/v1/environments/{env_id}",
        json={"name": "Stolen Name"},
        headers=headers_viewer,
    )
    assert update_env_bad.status_code == 403

    # Delete environment
    delete_env_bad = await client.delete(
        f"/api/v1/environments/{env_id}", headers=headers_viewer
    )
    assert delete_env_bad.status_code == 403

    # Create variable
    create_var_bad = await client.post(
        f"/api/v1/environments/{env_id}/variables",
        json={"key": "TOKEN", "value": "secret", "is_secret": False},
        headers=headers_viewer,
    )
    assert create_var_bad.status_code == 403

    # Update variable
    update_var_bad = await client.patch(
        f"/api/v1/environment-variables/{var_id}",
        json={"value": "stolen"},
        headers=headers_viewer,
    )
    assert update_var_bad.status_code == 403

    # Delete variable
    delete_var_bad = await client.delete(
        f"/api/v1/environment-variables/{var_id}", headers=headers_viewer
    )
    assert delete_var_bad.status_code == 403

    # 4. Assert reading succeeds for VIEWER
    get_envs = await client.get(
        f"/api/v1/workspaces/{ws_id}/environments", headers=headers_viewer
    )
    assert get_envs.status_code == 200

    get_vars = await client.get(
        f"/api/v1/environments/{env_id}/variables", headers=headers_viewer
    )
    assert get_vars.status_code == 200


@pytest.mark.anyio
async def test_11_test_tenant_isolation(client: AsyncClient):
    """
    Scenario 11: Test tenant isolation.
    Verifies that a user in Workspace B cannot access Workspace A's environment directly by UUID (returns 404).
    """
    # Create Workspace A + Environment
    owner_a_email = f"owner_a_{uuid.uuid4().hex[:6]}@example.com"
    headers_a, _ = await register_and_login(client, "Owner A", owner_a_email)
    ws_res_a = await client.post(
        "/api/v1/workspaces",
        json={"name": "Workspace A", "slug": f"ws-{uuid.uuid4().hex[:6]}"},
        headers=headers_a,
    )
    ws_id_a = ws_res_a.json()["id"]

    env_res_a = await client.post(
        f"/api/v1/workspaces/{ws_id_a}/environments",
        json={"name": "Development A"},
        headers=headers_a,
    )
    env_id_a = env_res_a.json()["id"]

    # Create Workspace B
    owner_b_email = f"owner_b_{uuid.uuid4().hex[:6]}@example.com"
    headers_b, _ = await register_and_login(client, "Owner B", owner_b_email)

    # Attempt to GET Workspace A's environment Development A using Workspace B's owner credentials
    bad_get = await client.get(f"/api/v1/environments/{env_id_a}", headers=headers_b)
    assert bad_get.status_code == 404  # Not found, isolation check succeeds.


@pytest.mark.anyio
async def test_12_test_encryption_at_rest(client: AsyncClient):
    """
    Scenario 12: Test encryption at rest.
    Verifies that variable values are stored as encrypted ciphertexts inside PostgreSQL,
    and decrypt_value safely recovers the plaintext value.
    """
    email = f"user_{uuid.uuid4().hex[:6]}@example.com"
    headers, _ = await register_and_login(client, "Owner User", email)

    ws_res = await client.post(
        "/api/v1/workspaces",
        json={"name": "Workspace A", "slug": f"ws-{uuid.uuid4().hex[:6]}"},
        headers=headers,
    )
    ws_id = ws_res.json()["id"]

    env_res = await client.post(
        f"/api/v1/workspaces/{ws_id}/environments",
        json={"name": "Development"},
        headers=headers,
    )
    env_id = env_res.json()["id"]

    var_res = await client.post(
        f"/api/v1/environments/{env_id}/variables",
        json={"key": "API_TOKEN", "value": "my-secret-token", "is_secret": True},
        headers=headers,
    )
    var_id = uuid.UUID(var_res.json()["id"])

    # Verify database values directly
    async with AsyncSessionLocal() as db:
        q = select(EnvironmentVariable).where(EnvironmentVariable.id == var_id)
        res = await db.execute(q)
        db_var = res.scalar_one_or_none()

        assert db_var is not None
        # Assert the stored value is NOT plaintext
        assert db_var.value_ciphertext != "my-secret-token"
        assert "my-secret-token" not in db_var.value_ciphertext

        # Assert ciphertext decrypts back to original value
        decrypted = decrypt_value(db_var.value_ciphertext)
        assert decrypted == "my-secret-token"
