from typing import Any

from pydantic import BaseModel, Field


class OpenAPIImportRequest(BaseModel):
    spec: dict[str, Any] = Field(..., min_length=1)
    collection_name: str | None = Field(default=None, min_length=1, max_length=120)


class DocumentationSummary(BaseModel):
    title: str
    version: str
    collection_count: int
    folder_count: int
    request_count: int
