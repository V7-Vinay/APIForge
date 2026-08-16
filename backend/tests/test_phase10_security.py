import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.redaction import redact_headers, redact_mapping, redact_url
from app.core.permissions import Permission, role_has_permission
from app.core.database import AsyncSessionLocal, engine
from app.models.workspace import WorkspaceRole
from app.models.audit_log import AuditLog

@pytest.fixture(autouse=True)
async def cleanup_connections():
    await engine.dispose()
    yield
    await engine.dispose()


def test_redacts_sensitive_mapping_keys():
    value = {
        "username": "alice",
        "password": "secret",
        "nested": {"api_key": "abc", "safe": "ok"},
    }
    result = redact_mapping(value)
    assert result["password"] == "[REDACTED]"
    assert result["nested"]["api_key"] == "[REDACTED]"
    assert result["nested"]["safe"] == "ok"


def test_redacts_sensitive_headers_and_url_query():
    headers = redact_headers({"Authorization": "Bearer secret", "Content-Type": "application/json"})
    assert headers["Authorization"] == "[REDACTED]"
    assert headers["Content-Type"] == "application/json"
    assert "secret" not in (redact_url("https://example.com?api_key=secret&name=alice") or "")


def test_audit_permission_is_admin_and_owner_only():
    assert role_has_permission(WorkspaceRole.OWNER, Permission.VIEW_AUDIT_LOGS)
    assert role_has_permission(WorkspaceRole.ADMIN, Permission.VIEW_AUDIT_LOGS)
    assert not role_has_permission(WorkspaceRole.EDITOR, Permission.VIEW_AUDIT_LOGS)
    assert not role_has_permission(WorkspaceRole.VIEWER, Permission.VIEW_AUDIT_LOGS)


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
async def test_security_headers_and_correlation_id(client: AsyncClient):
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.headers.get("X-Content-Type-Options") == "nosniff"
    assert response.headers.get("X-Frame-Options") == "DENY"
    assert response.headers.get("Referrer-Policy") == "no-referrer"
    assert "X-Request-ID" in response.headers
    
    # Custom request ID
    req_id = str(uuid.uuid4())
    resp2 = await client.get("/api/v1/health", headers={"X-Request-ID": req_id})
    assert resp2.headers.get("X-Request-ID") == req_id


@pytest.mark.anyio
async def test_audit_logging_and_rbac(client: AsyncClient):
    owner_email = f"owner_{uuid.uuid4().hex[:6]}@example.com"
    headers_owner, owner_id = await register_and_login(client, "Owner User", owner_email)

    # Create workspace (triggers audit log because POST /api/v1/workspaces)
    ws_res = await client.post(
        "/api/v1/workspaces",
        json={"name": "Audit WS", "slug": f"audit-ws-{uuid.uuid4().hex[:6]}"},
        headers=headers_owner,
    )
    assert ws_res.status_code == 201
    ws_id = ws_res.json()["id"]

    # Create collection (triggers audit log with workspace_id in URL)
    col_res = await client.post(
        f"/api/v1/workspaces/{ws_id}/collections",
        json={"name": "Audit Col"},
        headers=headers_owner,
    )
    assert col_res.status_code == 201

    # Verify audit logs in database
    async with AsyncSessionLocal() as db:
        # Query by user_id for general actions
        logs = await db.scalars(
            select(AuditLog).where(AuditLog.user_id == owner_id)
        )
        log_list = list(logs)
        assert len(log_list) >= 2
        assert any(log.action == "HTTP_POST" and "/workspaces" in log.path for log in log_list)

        # Query by workspace_id for workspace-specific actions
        logs_ws = await db.scalars(
            select(AuditLog).where(AuditLog.workspace_id == uuid.UUID(ws_id))
        )
        log_list_ws = list(logs_ws)
        assert len(log_list_ws) >= 1
        assert any(log.action == "HTTP_POST" and "/collections" in log.path for log in log_list_ws)

    # Try to view audit logs as OWNER
    audit_res = await client.get(
        f"/api/v1/workspaces/{ws_id}/audit-logs",
        headers=headers_owner,
    )
    assert audit_res.status_code == 200
    assert len(audit_res.json()) >= 1

    # Invite viewer
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

    # Viewer should be forbidden from accessing audit logs
    audit_viewer_res = await client.get(
        f"/api/v1/workspaces/{ws_id}/audit-logs",
        headers=headers_viewer,
    )
    assert audit_viewer_res.status_code == 403
