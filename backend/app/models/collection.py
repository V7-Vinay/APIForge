import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, Uuid, func, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Collection(Base):
    __tablename__ = "collections"
    __table_args__ = (
        Index("ix_collections_workspace_position", "workspace_id", "position"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
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

    folders = relationship(
        "Folder", back_populates="collection", cascade="all, delete-orphan"
    )
    requests = relationship(
        "APIRequest", back_populates="collection", cascade="all, delete-orphan"
    )
