import pytest
from pydantic import ValidationError
from app.schemas.resources import RequestCreate, AuthConfig


def test_request_schema_accepts_supported_method_and_url():
    request = RequestCreate(
        name="List users", method="get", url="https://example.com/users"
    )
    assert request.method == "GET"
    assert request.url == "https://example.com/users"


def test_request_schema_rejects_unsupported_method():
    with pytest.raises(ValidationError):
        RequestCreate(name="Trace", method="TRACE", url="https://example.com")


def test_auth_schema_requires_bearer_token():
    with pytest.raises(ValidationError):
        AuthConfig(type="bearer")
