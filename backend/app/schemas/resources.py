import uuid
from datetime import datetime
from typing import Literal

from pydantic import (
    AnyHttpUrl,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


class KeyValueItem(BaseModel):
    key: str = Field(min_length=1, max_length=200)
    value: str = Field(max_length=5000)
    enabled: bool = True

    @field_validator("key", "value", mode="before")
    @classmethod
    def trim(cls, value):
        return value.strip() if isinstance(value, str) else value


class AuthConfig(BaseModel):
    type: Literal["none", "bearer", "basic"] = "none"
    token: str | None = Field(default=None, max_length=10000)
    username: str | None = Field(default=None, max_length=500)
    password: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_auth(self):
        if self.type == "bearer" and not self.token:
            raise ValueError("Bearer authentication requires a token.")
        if self.type == "basic" and (self.username is None or self.password is None):
            raise ValueError("Basic authentication requires username and password.")
        if self.type == "none" and any(
            v is not None for v in (self.token, self.username, self.password)
        ):
            raise ValueError(
                "Authentication credentials are not allowed when type is none."
            )
        return self


class CollectionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=5000)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Name cannot be empty.")
        return value


class CollectionUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=5000)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("Name cannot be empty.")
        return value


class CollectionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    workspace_id: uuid.UUID
    name: str
    description: str | None
    position: int
    created_at: datetime
    updated_at: datetime


class FolderCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    parent_id: uuid.UUID | None = None

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Name cannot be empty.")
        return value


class FolderUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    parent_id: uuid.UUID | None = None

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("Name cannot be empty.")
        return value


class FolderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    collection_id: uuid.UUID
    parent_id: uuid.UUID | None
    name: str
    position: int
    created_at: datetime
    updated_at: datetime


SUPPORTED_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}


class RequestCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=5000)
    method: str
    url: str = Field(min_length=1, max_length=10000)
    headers: list[KeyValueItem] = Field(default_factory=list)
    query_params: list[KeyValueItem] = Field(default_factory=list)
    body: str | None = Field(default=None, max_length=2_000_000)
    auth_config: AuthConfig = Field(default_factory=AuthConfig)
    folder_id: uuid.UUID | None = None

    @field_validator("name", "url")
    @classmethod
    def clean_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Value cannot be empty.")
        return value

    @field_validator("method")
    @classmethod
    def validate_method(cls, value: str) -> str:
        value = value.strip().upper()
        if value not in SUPPORTED_METHODS:
            raise ValueError("Unsupported HTTP method.")
        return value

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        parsed = AnyHttpUrl(value)
        if parsed.scheme not in {"http", "https"}:
            raise ValueError("Only HTTP and HTTPS URLs are supported.")
        return str(parsed)


class RequestUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=5000)
    method: str | None = None
    url: str | None = Field(default=None, min_length=1, max_length=10000)
    headers: list[KeyValueItem] | None = None
    query_params: list[KeyValueItem] | None = None
    body: str | None = Field(default=None, max_length=2_000_000)
    auth_config: AuthConfig | None = None
    folder_id: uuid.UUID | None = None

    @field_validator("name", "url")
    @classmethod
    def clean_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("Value cannot be empty.")
        return value

    @field_validator("method")
    @classmethod
    def validate_optional_method(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip().upper()
        if value not in SUPPORTED_METHODS:
            raise ValueError("Unsupported HTTP method.")
        return value

    @field_validator("url")
    @classmethod
    def validate_optional_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        parsed = AnyHttpUrl(value)
        if parsed.scheme not in {"http", "https"}:
            raise ValueError("Only HTTP and HTTPS URLs are supported.")
        return str(parsed)


class RequestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    collection_id: uuid.UUID
    folder_id: uuid.UUID | None
    name: str
    description: str | None
    method: str
    url: str
    headers: list[dict] | None
    query_params: list[dict] | None
    body: str | None
    auth_config: dict | None
    position: int
    created_at: datetime
    updated_at: datetime


class ReorderPayload(BaseModel):
    position: int = Field(ge=0)
