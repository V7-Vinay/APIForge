"""Phase 11 deterministic unit coverage for security and core invariants."""

import pytest

from app.core.permissions import Permission, role_has_permission
from app.core.redaction import redact_headers, redact_mapping, redact_text, redact_url
from app.models.workspace import WorkspaceRole
from app.services.execution import ExecutionRuleError, _validate_url
from app.services.search import _pagination


pytestmark = pytest.mark.unit


def test_permission_matrix_is_explicit():
    assert role_has_permission(WorkspaceRole.OWNER, Permission.EXECUTE_REQUESTS)
    assert role_has_permission(WorkspaceRole.ADMIN, Permission.EXECUTE_REQUESTS)
    assert role_has_permission(WorkspaceRole.EDITOR, Permission.EXECUTE_REQUESTS)
    assert not role_has_permission(WorkspaceRole.VIEWER, Permission.EXECUTE_REQUESTS)

    assert role_has_permission(WorkspaceRole.OWNER, Permission.VIEW_HISTORY)
    assert role_has_permission(WorkspaceRole.ADMIN, Permission.VIEW_HISTORY)
    assert role_has_permission(WorkspaceRole.EDITOR, Permission.VIEW_HISTORY)
    assert role_has_permission(WorkspaceRole.VIEWER, Permission.VIEW_HISTORY)

    assert role_has_permission(WorkspaceRole.OWNER, Permission.VIEW_AUDIT_LOGS)
    assert role_has_permission(WorkspaceRole.ADMIN, Permission.VIEW_AUDIT_LOGS)
    assert not role_has_permission(WorkspaceRole.EDITOR, Permission.VIEW_AUDIT_LOGS)
    assert not role_has_permission(WorkspaceRole.VIEWER, Permission.VIEW_AUDIT_LOGS)


def test_redaction_is_recursive_and_preserves_safe_values():
    payload = {
        "name": "demo",
        "password": "secret",
        "nested": {"client_secret": "secret2", "enabled": True},
        "items": [{"token": "secret3", "label": "safe"}],
    }
    result = redact_mapping(payload)
    assert result == {
        "name": "demo",
        "password": "[REDACTED]",
        "nested": {"client_secret": "[REDACTED]", "enabled": True},
        "items": [{"token": "[REDACTED]", "label": "safe"}],
    }


def test_redaction_handles_json_text_headers_and_query_strings():
    text = redact_text('{"api_key":"secret","name":"demo"}')
    assert text is not None
    assert "secret" not in text
    assert "demo" in text

    headers = redact_headers({"Authorization": "Bearer secret", "Content-Type": "application/json"})
    assert headers["Authorization"] == "[REDACTED]"
    assert headers["Content-Type"] == "application/json"

    url = redact_url("https://example.com/path?api_key=secret&name=demo")
    assert url is not None
    assert "secret" not in url
    assert "name=demo" in url


def test_ssrf_url_policy_rejects_unsupported_schemes_and_credentials():
    assert _validate_url("https://example.com") == "https://example.com"
    assert _validate_url("http://example.com") == "http://example.com"

    for url, code in (
        ("ftp://example.com", "UNSUPPORTED_PROTOCOL"),
        ("file:///etc/passwd", "UNSUPPORTED_PROTOCOL"),
        ("https://user:pass@example.com", "INVALID_REQUEST_URL"),
    ):
        with pytest.raises(ExecutionRuleError) as exc:
            _validate_url(url)
        assert exc.value.code == code


def test_pagination_has_deterministic_metadata():
    assert _pagination(page=1, page_size=10, total=25) == {
        "page": 1,
        "page_size": 10,
        "total": 25,
        "total_pages": 3,
        "has_next": True,
        "has_previous": False,
    }
    assert _pagination(page=3, page_size=10, total=25) == {
        "page": 3,
        "page_size": 10,
        "total": 25,
        "total_pages": 3,
        "has_next": False,
        "has_previous": True,
    }
    assert _pagination(page=1, page_size=10, total=0) == {
        "page": 1,
        "page_size": 10,
        "total": 0,
        "total_pages": 0,
        "has_next": False,
        "has_previous": False,
    }
