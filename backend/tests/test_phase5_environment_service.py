from app.services.environments import validate_key


def test_valid_variable_keys():
    assert validate_key("BASE_URL") == "BASE_URL"
    assert validate_key("api.base-url") == "api.base-url"


def test_invalid_variable_key():
    import pytest

    with pytest.raises(Exception):
        validate_key("123BAD")
