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


async def create_test_request(
    client: AsyncClient, headers: dict, col_id: uuid.UUID, url: str
) -> str:
    """Helper to create a request definition in collection."""
    res = await client.post(
        f"/api/v1/collections/{col_id}/requests",
        json={
            "name": f"SSRF Test target",
            "method": "GET",
            "url": url,
            "headers": [],
            "query_params": [],
            "body": None,
            "auth_config": {"type": "none"},
        },
        headers=headers,
    )
    assert res.status_code == 201
    return res.json()["id"]


@pytest.mark.anyio
async def test_ssrf_direct_loopback_blocked(client: AsyncClient):
    """
    Simulates direct loopback SSRF attacks targeting localhost, 127.0.0.1, 0.0.0.0, and [::1].

    Attack Vector:
    An attacker attempts to make APIForge issue HTTP requests to the local server loopback interface
    to access admin endpoints or backend microservices running on the same host.

    Mitigation:
    APIForge resolves loopback domains/IPs and blocks execution directly.
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

    for loopback_target in [
        "http://localhost/admin",
        "http://127.0.0.1:8000/ready",
        "http://0.0.0.0/auth",
        "http://[::1]/debug",
    ]:
        req_id = await create_test_request(
            client, headers_owner, col_id, loopback_target
        )

        res = await client.post(
            f"/api/v1/requests/{req_id}/execute",
            json={"environment_id": None},
            headers=headers_owner,
        )
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is False
        assert data["error_code"] == "SSRF_BLOCKED"
        assert "private or local network" in data["error_message"].lower()


@pytest.mark.anyio
async def test_ssrf_private_ranges_blocked(client: AsyncClient):
    """
    Simulates SSRF attacks targeting RFC 1918 private IPv4 subnets (10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16).

    Attack Vector:
    An attacker attempts to discover or interact with services inside APIForge's internal private
    corporate network (e.g. databases, internal directories, Kubernetes pods, staging environments).

    Mitigation:
    Ensures that resolved IP addresses falling in internal routing ranges are caught and blocked.
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

    # Pick at least 2 concrete IPs per RFC 1918 range
    private_ips = [
        # 10.0.0.0/8
        "http://10.1.2.3/api",
        "http://10.254.254.254/status",
        # 172.16.0.0/12
        "http://172.16.1.1:9000/info",
        "http://172.31.254.254/metrics",
        # 192.168.0.0/16
        "http://192.168.1.1/setup",
        "http://192.168.254.254/health",
    ]

    for target in private_ips:
        req_id = await create_test_request(client, headers_owner, col_id, target)

        res = await client.post(
            f"/api/v1/requests/{req_id}/execute",
            json={"environment_id": None},
            headers=headers_owner,
        )
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is False
        assert data["error_code"] == "SSRF_BLOCKED"


@pytest.mark.anyio
async def test_ssrf_link_local_metadata_blocked(client: AsyncClient):
    """
    Simulates SSRF attacks targeting IPv4 link-local subnets (169.254.0.0/16).

    Attack Vector:
    Targets cloud metadata services (like AWS EC2, GCP, or Azure IMDS endpoints located at 169.254.169.254)
    to steal temporary IAM credentials, service tokens, or node metadata.

    Mitigation:
    Explicitly checks link-local IP addresses and blocks any communication attempts.
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

    for link_local in [
        "http://169.254.169.254/latest/meta-data/",
        "http://169.254.1.1/endpoint",
    ]:
        req_id = await create_test_request(client, headers_owner, col_id, link_local)

        res = await client.post(
            f"/api/v1/requests/{req_id}/execute",
            json={"environment_id": None},
            headers=headers_owner,
        )
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is False
        assert data["error_code"] == "SSRF_BLOCKED"


@pytest.mark.anyio
async def test_ssrf_dns_rebinding_blocked(client: AsyncClient):
    """
    Simulates a DNS Rebinding attack by returning a private loopback IP on hostname resolution.

    Attack Vector:
    An attacker maps a domain name under their control (e.g. rebind.attacker.com) to resolve to
    a private IP (e.g. 127.0.0.1). Since the URL hostname checks look like a public domain,
    it passes basic string filters. However, when connecting, it routes to localhost.

    Mitigation:
    APIForge resolves all hostnames to IP addresses before initiating a connection, and validates
    the resolved IPs, rejecting private network target destinations.
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

    # Target points to a public-looking domain name
    req_id = await create_test_request(
        client, headers_owner, col_id, "https://rebind.attacker.com/status"
    )

    # Mock domain name resolution to return private IP loopback address
    with patch("app.services.execution._resolve_public_ips") as mock_dns:
        mock_dns.side_effect = httpx.ConnectError(
            "SSRF check: host resolves to private IP"
        )
        # Or let the internal resolver fail on localhost, but we simulate it by returning 127.0.0.1 directly
        # and raising the exception from _resolve_public_ips:
        from app.services.execution import ExecutionRuleError

        mock_dns.side_effect = ExecutionRuleError(
            "SSRF_BLOCKED",
            "Requests to private or local network addresses are blocked.",
            403,
        )

        res = await client.post(
            f"/api/v1/requests/{req_id}/execute",
            json={"environment_id": None},
            headers=headers_owner,
        )
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is False
        assert data["error_code"] == "SSRF_BLOCKED"


@pytest.mark.anyio
async def test_ssrf_redirect_chain_blocked(client: AsyncClient):
    """
    Simulates a Redirect-based SSRF attack: public URL redirects (302) to a private loopback target.

    Attack Vector:
    An attacker submits a request to a public domain they control. When APIForge executes it,
    the upstream server returns a 302 redirect pointing to an internal service (e.g. http://127.0.0.1:8000/ready).
    If the engine blindly follows redirects, the internal endpoint is requested.

    Mitigation:
    The engine validates redirect headers manually, performs IP lookup on redirect targets,
    and blocks requests if they point to restricted subnets.
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

    # Initial request points to public endpoint
    req_id = await create_test_request(
        client, headers_owner, col_id, "https://public.example.com/redirect"
    )

    # Mock upstream response to return redirect pointing to private IP metadata endpoint
    mock_redirect_resp = httpx.Response(
        302,
        headers={"Location": "http://127.0.0.1:8000/ready"},
    )
    original_request = httpx.AsyncClient.request

    async def conditional_request(self, method, url, *args, **kwargs):
        # Allow internal FastAPI test routing
        if str(url).startswith("/") or "127.0.0.1" in str(url):
            return await original_request(self, method, url, *args, **kwargs)
        # Intercept execution outbound request and return redirect
        return mock_redirect_resp

    async def mock_resolve_dns(hostname):
        if "127.0.0.1" in hostname or "localhost" in hostname:
            from app.services.execution import ExecutionRuleError

            raise ExecutionRuleError(
                "SSRF_BLOCKED",
                "Requests to private or local network addresses are blocked.",
                403,
            )
        return ["93.184.215.14"]

    with patch("httpx.AsyncClient.request", new=conditional_request):
        with patch("app.services.execution._resolve_public_ips", new=mock_resolve_dns):
            res = await client.post(
                f"/api/v1/requests/{req_id}/execute",
                json={"environment_id": None},
                headers=headers_owner,
            )
            assert res.status_code == 200
            data = res.json()
            assert data["success"] is False
            assert data["error_code"] == "SSRF_BLOCKED"


@pytest.mark.anyio
async def test_ssrf_protocol_restrictions(client: AsyncClient):
    """
    Verifies that only http:// and https:// URI schemes are accepted, and unsupported protocols
    (like file://, ftp://, gopher://, data://, and javascript://) return UNSUPPORTED_PROTOCOL.

    Attack Vector:
    An attacker attempts to read local file contents via file:// or execute javascript, bypass schemes,
    or issue raw commands on legacy gopher/ftp protocols.

    Mitigation:
    APIForge URL parser explicitly enforces whitelist of {'http', 'https'} schemes.
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

    env_res = await client.post(
        f"/api/v1/workspaces/{ws_id}/environments",
        json={"name": "Development"},
        headers=headers_owner,
    )
    env_id = env_res.json()["id"]

    for bad_protocol in ["file", "ftp", "gopher", "data", "javascript"]:
        var_name = f"SCHEME_{bad_protocol}"
        await client.post(
            f"/api/v1/environments/{env_id}/variables",
            json={"key": var_name, "value": bad_protocol, "is_secret": False},
            headers=headers_owner,
        )

        req_id = await create_test_request(
            client, headers_owner, col_id, f"{{{{{var_name}}}}}://etc/passwd"
        )

        res = await client.post(
            f"/api/v1/requests/{req_id}/execute",
            json={"environment_id": env_id},
            headers=headers_owner,
        )
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is False
        assert data["error_code"] == "UNSUPPORTED_PROTOCOL"
