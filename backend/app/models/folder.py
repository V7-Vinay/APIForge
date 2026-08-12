import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Uuid, func, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Folder(Base):
    __tablename__ = "folders"
    __table_args__ = (
        Index("ix_folders_collection_position", "collection_id", "position"),
        Index("ix_folders_parent_id", "parent_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    collection_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("collections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("folders.id", ondelete="CASCADE"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
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

    collection = relationship("Collection", back_populates="folders")
    parent = relationship("Folder", remote_side=[id], back_populates="children")
    children = relationship(
        "Folder", back_populates="parent", cascade="all, delete-orphan"
    )
    requests = relationship("APIRequest", back_populates="folder")
