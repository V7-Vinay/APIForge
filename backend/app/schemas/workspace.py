import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.workspace import WorkspaceRole


class WorkspaceCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    slug: str = Field(
        min_length=2, max_length=140, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$"
    )


class WorkspaceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)


class WorkspaceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime


class WorkspaceMemberResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    email: str
    role: WorkspaceRole
    created_at: datetime


class WorkspaceMemberRoleUpdate(BaseModel):
    role: WorkspaceRole
