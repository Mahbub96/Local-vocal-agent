from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.sqlite.base import Base


class Metadata(Base):
    __tablename__ = "metadata"
    __table_args__ = (
        Index("idx_metadata_session_id", "session_id"),
        Index("idx_metadata_message_id", "message_id"),
        Index("idx_metadata_key", "key"),
        Index("idx_metadata_key_value", "key", "value"),
    )

    id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    session_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=True
    )
    message_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("messages.id", ondelete="CASCADE"), nullable=True
    )
    key: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    value_type: Mapped[str] = mapped_column(String(32), default="text", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    session: Mapped["Session | None"] = relationship(
        "Session", back_populates="metadata_entries"
    )
    message: Mapped["Message | None"] = relationship(
        "Message", back_populates="metadata_entries"
    )
