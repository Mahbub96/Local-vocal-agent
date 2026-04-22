from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.sqlite.base import Base


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (
        UniqueConstraint("session_id", "sequence_number", name="uq_messages_session_sequence"),
        Index("idx_messages_session_id_seq", "session_id", "sequence_number"),
        Index("idx_messages_created_at", "created_at"),
        Index("idx_messages_role", "role"),
        Index("idx_messages_parent_message_id", "parent_message_id"),
    )

    id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    session_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_type: Mapped[str] = mapped_column(
        String(32), default="text", nullable=False
    )
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)
    parent_message_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("messages.id", ondelete="SET NULL"), nullable=True
    )
    tool_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    tool_input: Mapped[str | None] = mapped_column(Text, nullable=True)
    tool_output: Mapped[str | None] = mapped_column(Text, nullable=True)
    token_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    session: Mapped["Session"] = relationship("Session", back_populates="messages")
    parent_message: Mapped["Message | None"] = relationship(
        "Message", remote_side="Message.id"
    )
    metadata_entries: Mapped[list["Metadata"]] = relationship(
        "Metadata",
        back_populates="message",
        cascade="all, delete-orphan",
    )
