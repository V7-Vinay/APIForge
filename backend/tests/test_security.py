import uuid
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_password_hash_is_not_plaintext():
    password = "CorrectHorseBatteryStaple123!"
    hashed = hash_password(password)
    assert hashed != password
    assert verify_password(password, hashed)
    assert not verify_password("wrong-password", hashed)


def test_access_token_contains_expected_claims():
    user_id = uuid.uuid4()
    payload = decode_access_token(create_access_token(user_id))
    assert payload["sub"] == str(user_id)
    assert payload["type"] == "access"
    assert payload["exp"] > payload["iat"]
