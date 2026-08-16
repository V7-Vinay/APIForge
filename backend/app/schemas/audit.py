import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID | None
    workspace_id: uuid.UUID | None
    action: str
    method: str
    path: str
    status_code: int
    resource_type: str | None
    resource_id: uuid.UUID | None
    ip_address: str | None
    user_agent: str | None
    metadata_json: dict
    created_at: datetime
