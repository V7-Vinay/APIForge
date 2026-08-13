import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class PaginationParams(BaseModel):
    page: int = Field(default=1, ge=1, le=10_000)
    page_size: int = Field(default=20, ge=1, le=100)


class SearchResponseItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    resource_type: Literal["collection", "folder", "request"]
    name: str
    description: str | None = None
    collection_id: uuid.UUID | None = None
    folder_id: uuid.UUID | None = None
    method: str | None = None
    url: str | None = None
    position: int = 0
    created_at: datetime
    updated_at: datetime


class SearchResponse(BaseModel):
    items: list[SearchResponseItem]
    page: int
    page_size: int
    total: int
    total_pages: int
    has_next: bool
    has_previous: bool


class PaginatedCollectionResponse(BaseModel):
    items: list[dict]
    page: int
    page_size: int
    total: int
    total_pages: int
    has_next: bool
    has_previous: bool


class PaginatedRequestResponse(BaseModel):
    items: list[dict]
    page: int
    page_size: int
    total: int
    total_pages: int
    has_next: bool
    has_previous: bool
