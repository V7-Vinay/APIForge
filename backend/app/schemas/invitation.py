import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator
from app.models.workspace import WorkspaceRole


class WorkspaceInvitationCreate(BaseModel):
    email: EmailStr
    role: WorkspaceRole

    @field_validator("role")
    @classmethod
    def validate_role(cls, value: WorkspaceRole) -> WorkspaceRole:
        if value == WorkspaceRole.OWNER:
            raise ValueError("Invitations cannot assign the OWNER role.")
        return value


class WorkspaceInvitationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workspace_id: uuid.UUID
    email: str
    role: WorkspaceRole
    expires_at: datetime
    created_at: datetime
    accepted_at: datetime | None
