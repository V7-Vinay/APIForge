import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ExecutionHistoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    request_id: uuid.UUID
    environment_id: uuid.UUID | None
    method: str
    url: str
    status_code: int | None
    success: bool
    duration_ms: float | None
    response_size_bytes: int
    response_headers: dict[str, str]
    response_body: str | None
    content_type: str | None
    error_code: str | None
    error_message: str | None
    created_at: datetime
