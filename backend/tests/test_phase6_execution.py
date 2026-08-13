import pytest

from app.services.execution import ExecutionRuleError, _validate_url


def test_only_http_and_https_are_allowed():
    assert _validate_url("https://example.com/api") == "https://example.com/api"
    assert _validate_url("http://example.com") == "http://example.com"
    for url in ("file:///etc/passwd", "ftp://example.com", "gopher://example.com"):
        with pytest.raises(ExecutionRuleError) as exc:
            _validate_url(url)
        assert exc.value.code == "UNSUPPORTED_PROTOCOL"


def test_credentials_in_url_are_rejected():
    with pytest.raises(ExecutionRuleError) as exc:
        _validate_url("https://user:password@example.com")
    assert exc.value.code == "INVALID_REQUEST_URL"


def test_missing_hostname_is_rejected():
    with pytest.raises(ExecutionRuleError) as exc:
        _validate_url("https://")
    assert exc.value.code == "INVALID_REQUEST_URL"


@pytest.mark.asyncio
async def test_localhost_is_blocked():
    from app.services.execution import _resolve_public_ips

    with pytest.raises(ExecutionRuleError) as exc:
        await _resolve_public_ips("localhost")
    assert exc.value.code == "SSRF_BLOCKED"


@pytest.mark.asyncio
async def test_loopback_ip_is_blocked():
    from app.services.execution import _resolve_public_ips

    with pytest.raises(ExecutionRuleError) as exc:
        await _resolve_public_ips("127.0.0.1")
    assert exc.value.code == "SSRF_BLOCKED"
