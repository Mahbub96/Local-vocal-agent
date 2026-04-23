from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import get_settings
from app.memory.short_term.cache import short_term_memory_store
from app.models import Message, Session


settings = get_settings()


@dataclass(slots=True)
class MemoryContext:
    """Structured memory bundle injected into downstream orchestration."""

    session_id: str
    short_term_messages: list[dict[str, str]]
    long_term_messages: list[Message]


class MemoryService:
    """Coordinates short-term cache reads and durable SQLite-backed history."""

    def __init__(self, db_session: AsyncSession) -> None:
        self.db_session = db_session
        self.short_term_store = short_term_memory_store

    async def get_or_create_session(
        self,
        session_id: str | None = None,
        *,
        title: str | None = None,
        user_id: str | None = None,
    ) -> Session:
        if session_id:
            session = await self.db_session.get(Session, session_id)
            if session is not None:
                return session

        session = Session(title=title, user_id=user_id)
        self.db_session.add(session)
        await self.db_session.commit()
        await self.db_session.refresh(session)
        return session

    async def get_recent_messages(
        self, session_id: str, *, limit: int | None = None
    ) -> list[Message]:
        query_limit = limit or settings.short_term_message_limit
        statement: Select[tuple[Message]] = (
            select(Message)
            .where(Message.session_id == session_id)
            .order_by(Message.sequence_number.desc())
            .limit(query_limit)
        )
        result = await self.db_session.execute(statement)
        messages = list(reversed(result.scalars().all()))
        self.short_term_store.clear(session_id)
        self.short_term_store.extend(
            session_id,
            [{"role": message.role, "content": message.content} for message in messages],
        )
        return messages

    async def add_message(
        self,
        session_id: str,
        *,
        role: str,
        content: str,
        content_type: str = "text",
        parent_message_id: str | None = None,
        tool_name: str | None = None,
        tool_input: str | None = None,
        tool_output: str | None = None,
        token_count: int | None = None,
    ) -> Message:
        sequence_number = await self._next_sequence_number(session_id)
        message = Message(
            session_id=session_id,
            role=role,
            content=content,
            content_type=content_type,
            sequence_number=sequence_number,
            parent_message_id=parent_message_id,
            tool_name=tool_name,
            tool_input=tool_input,
            tool_output=tool_output,
            token_count=token_count,
        )
        self.db_session.add(message)

        session = await self.db_session.get(Session, session_id)
        if session is not None:
            session.last_message_at = func.now()

        await self.db_session.commit()
        await self.db_session.refresh(message)

        self.short_term_store.append(session_id, role=role, content=content)
        return message

    async def build_context(
        self,
        session_id: str,
        *,
        long_term_messages: list[Message] | None = None,
    ) -> MemoryContext:
        short_term_messages = self.short_term_store.get(session_id)
        if not short_term_messages:
            recent_messages = await self.get_recent_messages(session_id)
            short_term_messages = [
                {"role": message.role, "content": message.content}
                for message in recent_messages
            ]

        long_term_context = self._prepare_long_term_context(
            short_term_messages=short_term_messages,
            long_term_messages=long_term_messages or [],
        )
        return MemoryContext(
            session_id=session_id,
            short_term_messages=short_term_messages,
            long_term_messages=long_term_context,
        )

    async def fetch_messages_by_ids(self, message_ids: list[str]) -> list[Message]:
        if not message_ids:
            return []

        statement: Select[tuple[Message]] = select(Message).where(Message.id.in_(message_ids))
        result = await self.db_session.execute(statement)
        messages = result.scalars().all()
        message_order = {message_id: index for index, message_id in enumerate(message_ids)}
        return sorted(messages, key=lambda message: message_order.get(message.id, 0))

    async def fetch_session_messages(
        self, session_id: str, *, limit: int | None = None
    ) -> list[Message]:
        statement: Select[tuple[Message]] = (
            select(Message)
            .where(Message.session_id == session_id)
            .order_by(Message.sequence_number.asc())
        )
        if limit:
            statement = statement.limit(limit)

        result = await self.db_session.execute(statement)
        return result.scalars().all()

    def serialize_messages(
        self, messages: list[Message], *, max_items: int | None = None
    ) -> list[dict[str, Any]]:
        subset = messages[-max_items:] if max_items else messages
        return [
            {
                "id": message.id,
                "session_id": message.session_id,
                "role": message.role,
                "content": message.content,
                "content_type": message.content_type,
                "sequence_number": message.sequence_number,
                "created_at": message.created_at.isoformat()
                if message.created_at
                else None,
                "tool_name": message.tool_name,
            }
            for message in subset
        ]

    async def _next_sequence_number(self, session_id: str) -> int:
        statement = select(func.max(Message.sequence_number)).where(
            Message.session_id == session_id
        )
        result = await self.db_session.execute(statement)
        max_sequence = result.scalar_one_or_none()
        return (max_sequence or 0) + 1

    def _prepare_long_term_context(
        self,
        *,
        short_term_messages: list[dict[str, str]],
        long_term_messages: list[Message],
    ) -> list[Message]:
        """Deduplicate and cap semantic memory before prompt injection."""
        if not long_term_messages:
            return []

        short_term_signatures = {
            f"{message['role']}::{message['content'].strip()}"
            for message in short_term_messages
            if message.get("content")
        }
        deduped: list[Message] = []
        seen_ids: set[str] = set()
        for message in long_term_messages:
            if message.id in seen_ids:
                continue
            signature = f"{message.role}::{message.content.strip()}"
            if signature in short_term_signatures:
                continue
            seen_ids.add(message.id)
            deduped.append(message)
            if len(deduped) >= settings.memory_top_k:
                break
        return deduped
