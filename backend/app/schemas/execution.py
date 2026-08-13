import uuid
from pydantic import BaseModel


class ExecuteRequest(BaseModel):
    environment_id: uuid.UUID | None = None


class ExecutionResponse(BaseModel):
    success: bool
    status_code: int | None = None
    headers: dict[str, str] | None = None
    body: str | None = None
    content_type: str | None = None
    response_size_bytes: int | None = None
    body_is_text: bool | None = None
    duration_ms: float | None = None
    redirects: int | None = None
    error_code: str | None = None
    error_message: str | None = None
