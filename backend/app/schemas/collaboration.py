import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class CollaborationEventType(str, Enum):
    AUTHENTICATED = "AUTHENTICATED"
    USER_JOINED_REQUEST = "USER_JOINED_REQUEST"
    USER_LEFT_REQUEST = "USER_LEFT_REQUEST"
    PRESENCE_SNAPSHOT = "PRESENCE_SNAPSHOT"
    REQUEST_UPDATED = "REQUEST_UPDATED"
    COLLECTION_UPDATED = "COLLECTION_UPDATED"
    ERROR = "ERROR"


class CollaborationEvent(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    type: CollaborationEventType
    workspace_id: uuid.UUID
    actor_id: uuid.UUID | None = None
    request_id: uuid.UUID | None = None
    resource_id: uuid.UUID | None = None
    resource_type: str | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    payload: dict[str, Any] = Field(default_factory=dict)


class CollaborationClientMessage(BaseModel):
    type: Literal["AUTH", "JOIN_REQUEST", "LEAVE_REQUEST", "PING"]
    token: str | None = None
    request_id: uuid.UUID | None = None
