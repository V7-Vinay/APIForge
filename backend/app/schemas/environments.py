import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field, field_validator


class EnvironmentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=1000)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Environment name cannot be empty.")
        return value


class EnvironmentUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=1000)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("Environment name cannot be empty.")
        return value


class EnvironmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    workspace_id: uuid.UUID
    name: str
    description: str | None
    created_at: datetime
    updated_at: datetime


class VariableCreate(BaseModel):
    key: str = Field(min_length=1, max_length=100)
    value: str = Field(max_length=10000)
    is_secret: bool = False


class VariableUpdate(BaseModel):
    key: str | None = Field(default=None, min_length=1, max_length=100)
    value: str | None = Field(default=None, max_length=10000)
    is_secret: bool | None = None


class VariableResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    environment_id: uuid.UUID
    key: str
    is_secret: bool
    created_at: datetime
    updated_at: datetime


class VariableRevealResponse(VariableResponse):
    value: str


class ResolveRequest(BaseModel):
    text: str = Field(max_length=50000)


class ResolveResponse(BaseModel):
    resolved_text: str
