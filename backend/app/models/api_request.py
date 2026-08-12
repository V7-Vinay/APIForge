import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    Uuid,
    func,
    Index,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class HTTPMethod(str, Enum):
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"
    HEAD = "HEAD"
    OPTIONS = "OPTIONS"


class APIRequest(Base):
    __tablename__ = "requests"
    __table_args__ = (
        Index("ix_requests_collection_position", "collection_id", "position"),
        Index("ix_requests_folder_id", "folder_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    collection_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("collections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    folder_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("folders.id", ondelete="SET NULL"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    method: Mapped[str] = mapped_column(String(10), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    headers: Mapped[list | None] = mapped_column(JSON, nullable=True)
    query_params: Mapped[list | None] = mapped_column(JSON, nullable=True)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    auth_config: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    collection = relationship("Collection", back_populates="requests")
    folder = relationship("Folder", back_populates="requests")
