import uuid
from datetime import datetime, timezone
import pytest
from httpx import AsyncClient

from app.services.search import _pagination
from app.core.database import AsyncSessionLocal, engine


@pytest.fixture(autouse=True)
async def cleanup_connections():
    """Dispose the engine connections to prevent event loop mismatch across tests."""
    await engine.dispose()
    yield
    await engine.dispose()


@pytest.fixture(autouse=True)
async def init_redis_for_loop():
    """Re-initialize Redis client for the current event loop of each test."""
    import app.core.redis as app_redis
    from app.core.config import settings
    from redis.asyncio import Redis

    app_redis.redis_client = Redis.from_url(settings.REDIS_URL, decode_responses=True)
    yield
    if app_redis.redis_client is not None:
        await app_redis.redis_client.aclose()


async def register_and_login(
    client: AsyncClient, name: str, email: str
) -> tuple[dict[str, str], uuid.UUID]:
    """Helper function to register and login a user, returning auth headers and user ID."""
    reg = await client.post(
        "/api/v1/auth/register",
        json={"name": name, "email": email, "password": "securepassword123"},
    )
    assert reg.status_code == 201
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "securepassword123"},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]
    me = await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    return {"Authorization": f"Bearer {token}"}, uuid.UUID(me.json()["id"])


@pytest.mark.anyio
async def test_pagination_first_page():
    assert _pagination(1, 20, 45) == {
        "page": 1,
        "page_size": 20,
        "total": 45,
        "total_pages": 3,
        "has_next": True,
        "has_previous": False,
    }


@pytest.mark.anyio
async def test_pagination_last_page():
    meta = _pagination(3, 20, 45)
    assert meta["has_next"] is False
    assert meta["has_previous"] is True


@pytest.mark.anyio
async def test_empty_pagination():
    meta = _pagination(1, 20, 0)
    assert meta["total_pages"] == 0
    assert meta["has_next"] is False
    assert meta["has_previous"] is False


@pytest.mark.anyio
async def test_search_workspace_endpoints(client: AsyncClient):
    """
    Verifies the cross-resource workspace search endpoint GET /workspaces/{id}/search
    with search string filtering, type restrictions, sorting, and pagination metadata.
    """
    owner_email = f"owner_{uuid.uuid4().hex[:6]}@example.com"
    headers, _ = await register_and_login(client, "Owner User", owner_email)

    # Create Workspace
    ws_res = await client.post(
        "/api/v1/workspaces",
        json={"name": "Workspace A", "slug": f"ws-{uuid.uuid4().hex[:6]}"},
        headers=headers,
    )
    ws_id = ws_res.json()["id"]

    # Create Collection
    col_res = await client.post(
        f"/api/v1/workspaces/{ws_id}/collections",
        json={
            "name": "User Profiles Collection",
            "description": "Manage user database profile collections",
        },
        headers=headers,
    )
    col_id = col_res.json()["id"]

    # Create Folder
    fold_res = await client.post(
        f"/api/v1/collections/{col_id}/folders",
        json={"name": "Auth Middleware Folder", "parent_id": None},
        headers=headers,
    )
    fold_id = fold_res.json()["id"]

    # Create Request
    req_res = await client.post(
        f"/api/v1/collections/{col_id}/requests",
        json={
            "name": "Register User Endpoint",
            "method": "POST",
            "url": "https://api.example.com/register",
            "folder_id": fold_id,
        },
        headers=headers,
    )
    req_id = req_res.json()["id"]

    # 1. Search Query cross-resource matches
    res = await client.get(f"/api/v1/workspaces/{ws_id}/search?q=User", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert (
        len(data["items"]) == 2
    )  # Match "User Profiles Collection" & "Register User Endpoint"
    types = {item["resource_type"] for item in data["items"]}
    assert "collection" in types
    assert "request" in types

    # 2. Match folder specifically
    res = await client.get(f"/api/v1/workspaces/{ws_id}/search?q=Auth", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert len(data["items"]) == 1
    assert data["items"][0]["resource_type"] == "folder"
    assert data["items"][0]["name"] == "Auth Middleware Folder"

    # 3. Restrict by resource_type
    res = await client.get(
        f"/api/v1/workspaces/{ws_id}/search?q=User&resource_type=request",
        headers=headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert len(data["items"]) == 1
    assert data["items"][0]["resource_type"] == "request"
    assert data["items"][0]["name"] == "Register User Endpoint"

    # 4. Paginate search result
    res = await client.get(
        f"/api/v1/workspaces/{ws_id}/search?q=User&page=1&page_size=1", headers=headers
    )
    assert res.status_code == 200
    data = res.json()
    assert len(data["items"]) == 1
    assert data["page"] == 1
    assert data["page_size"] == 1
    assert data["total"] == 2
    assert data["total_pages"] == 2
    assert data["has_next"] is True
    assert data["has_previous"] is False


@pytest.mark.anyio
async def test_paginated_collections_and_requests(client: AsyncClient):
    """
    Verifies dedicated offset-limit database-level paginated collection and request listing.
    """
    owner_email = f"owner_{uuid.uuid4().hex[:6]}@example.com"
    headers, _ = await register_and_login(client, "Owner User", owner_email)

    ws_res = await client.post(
        "/api/v1/workspaces",
        json={"name": "Workspace B", "slug": f"ws-{uuid.uuid4().hex[:6]}"},
        headers=headers,
    )
    ws_id = ws_res.json()["id"]

    # Create 3 Collections
    for i in range(3):
        await client.post(
            f"/api/v1/workspaces/{ws_id}/collections",
            json={"name": f"Collection {i}"},
            headers=headers,
        )

    # 1. Fetch paginated collections
    res = await client.get(
        f"/api/v1/workspaces/{ws_id}/collections/page?page=1&page_size=2&sort_by=name&sort_order=asc",
        headers=headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert len(data["items"]) == 2
    assert data["total"] == 3
    assert data["total_pages"] == 2
    assert data["items"][0]["name"] == "Collection 0"
    assert data["items"][1]["name"] == "Collection 1"


@pytest.mark.anyio
async def test_search_security_and_tenant_isolation(client: AsyncClient):
    """
    Verifies that search/pagination endpoints enforce strict workspace membership access rules.
    """
    owner_email = f"owner_{uuid.uuid4().hex[:6]}@example.com"
    headers_owner, _ = await register_and_login(client, "Owner User", owner_email)

    other_email = f"other_{uuid.uuid4().hex[:6]}@example.com"
    headers_other, _ = await register_and_login(client, "Other User", other_email)

    # Create Workspace A as Owner
    ws_res = await client.post(
        "/api/v1/workspaces",
        json={"name": "Workspace A", "slug": f"ws-{uuid.uuid4().hex[:6]}"},
        headers=headers_owner,
    )
    ws_id_a = ws_res.json()["id"]

    # Other User tries to search Workspace A (Access blocked)
    res = await client.get(
        f"/api/v1/workspaces/{ws_id_a}/search?q=test", headers=headers_other
    )
    assert res.status_code == 404
