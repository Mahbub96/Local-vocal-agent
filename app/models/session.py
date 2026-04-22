from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.sqlite.base import Base


class Session(Base):
    __tablename__ = "sessions"
    __table_args__ = (
        Index("idx_sessions_updated_at", "updated_at"),
        Index("idx_sessions_last_message_at", "last_message_at"),
        Index("idx_sessions_user_id", "user_id"),
    )

    id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    user_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        index=True,
    )
    last_message_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    is_active: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    messages: Mapped[list["Message"]] = relationship(
        "Message",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="Message.sequence_number",
    )
    metadata_entries: Mapped[list["Metadata"]] = relationship(
        "Metadata",
        back_populates="session",
        cascade="all, delete-orphan",
    )
