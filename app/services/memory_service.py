from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from sqlalchemy import Select, case, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import get_settings
from app.memory.short_term.cache import short_term_memory_store
from app.models import Message, Metadata, Session
from app.services.effective_assistant_prefs import EffectiveAssistantPrefs, resolve_effective_assistant_prefs


settings = get_settings()


@dataclass(slots=True)
class MemoryContext:
    """Structured memory bundle injected into downstream orchestration."""

    session_id: str
    short_term_messages: list[dict[str, str]]
    long_term_messages: list[Message]
    user_profile: dict[str, Any] | None = None
    effective_prefs: EffectiveAssistantPrefs | None = None


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
                if user_id and session.user_id != user_id:
                    session.user_id = user_id
                    await self.db_session.commit()
                    await self.db_session.refresh(session)
                return session

        session = Session(title=title, user_id=user_id)
        self.db_session.add(session)
        await self.db_session.commit()
        await self.db_session.refresh(session)
        return session

    async def get_recent_messages(
        self, session_id: str, *, limit: int | None = None
    ) -> list[Message]:
        query_limit = limit if limit is not None else settings.short_term_message_limit
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

        return message

    async def build_context(
        self,
        session_id: str,
        *,
        long_term_messages: list[Message] | None = None,
        user_id: str | None = None,
        effective_prefs: EffectiveAssistantPrefs | None = None,
        cached_profile: dict[str, Any] | None = None,
        recent_messages_cached: list[Message] | None = None,
    ) -> MemoryContext:
        profile: dict[str, Any] | None = None
        if user_id:
            if cached_profile is not None:
                profile = cached_profile
            else:
                p = await self.get_user_profile(user_id)
                profile = p if p else None
        eff = effective_prefs or resolve_effective_assistant_prefs(profile)
        st_limit = eff.short_term_message_limit

        if recent_messages_cached is not None:
            rows = (
                recent_messages_cached[-st_limit:]
                if len(recent_messages_cached) > st_limit
                else recent_messages_cached
            )
            short_term_messages = [
                {"role": message.role, "content": message.content} for message in rows
            ]
        else:
            # Indexed session_id + sequence_number — durable history for the LLM.
            recent_messages = await self.get_recent_messages(session_id, limit=st_limit)
            short_term_messages = [
                {"role": message.role, "content": message.content}
                for message in recent_messages
            ]

        long_term_context = self._prepare_long_term_context(
            short_term_messages=short_term_messages,
            long_term_messages=long_term_messages or [],
            memory_top_k_cap=eff.memory_top_k,
        )
        return MemoryContext(
            session_id=session_id,
            short_term_messages=short_term_messages,
            long_term_messages=long_term_context,
            user_profile=profile,
            effective_prefs=eff,
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
        """Return messages in chronological order. With ``limit``, the **latest** N turns (not the oldest)."""
        if limit is None:
            statement: Select[tuple[Message]] = (
                select(Message)
                .where(Message.session_id == session_id)
                .order_by(Message.sequence_number.asc())
            )
            result = await self.db_session.execute(statement)
            return result.scalars().all()

        statement = (
            select(Message)
            .where(Message.session_id == session_id)
            .order_by(Message.sequence_number.desc())
            .limit(limit)
        )
        result = await self.db_session.execute(statement)
        rows = list(result.scalars().all())
        rows.reverse()
        return rows

    async def list_sessions(
        self,
        *,
        user_id: str | None = None,
        limit: int = 20,
        is_active: int = 1,
    ) -> list[Session]:
        statement: Select[tuple[Session]] = select(Session).where(Session.is_active == is_active)
        if user_id:
            statement = statement.where(Session.user_id == user_id)
        statement = statement.order_by(desc(Session.last_message_at), desc(Session.created_at)).limit(
            limit
        )
        result = await self.db_session.execute(statement)
        return result.scalars().all()

    async def get_session(self, session_id: str) -> Session | None:
        return await self.db_session.get(Session, session_id)

    async def update_session(
        self,
        session_id: str,
        *,
        title: str | None = None,
        is_active: int | None = None,
    ) -> Session | None:
        session = await self.db_session.get(Session, session_id)
        if session is None:
            return None

        if title is not None:
            normalized_title = title.strip()
            session.title = normalized_title or None
        if is_active is not None:
            session.is_active = is_active

        await self.db_session.commit()
        await self.db_session.refresh(session)
        return session

    async def archive_session(self, session_id: str) -> Session | None:
        session = await self.db_session.get(Session, session_id)
        if session is None:
            return None
        session.is_active = 0
        await self.db_session.commit()
        await self.db_session.refresh(session)
        return session

    async def restore_session(self, session_id: str) -> Session | None:
        session = await self.db_session.get(Session, session_id)
        if session is None:
            return None
        session.is_active = 1
        await self.db_session.commit()
        await self.db_session.refresh(session)
        return session

    async def delete_session_permanently(self, session_id: str) -> bool | None:
        session = await self.db_session.get(Session, session_id)
        if session is None:
            return None
        if session.is_active != 0:
            return False
        await self.db_session.delete(session)
        await self.db_session.commit()
        return True

    async def count_session_messages(self, session_id: str) -> int:
        statement = select(func.count(Message.id)).where(Message.session_id == session_id)
        result = await self.db_session.execute(statement)
        return int(result.scalar() or 0)

    async def search_user_messages_keyword(
        self,
        user_id: str,
        query: str,
        *,
        limit: int,
        min_word_len: int,
    ) -> list[Message]:
        """
        Substring recall across every session for this user (complements vector search).
        Terms are alphanumeric / Bangla script tokens from the query.
        """
        raw = (query or "").strip()
        if not raw or limit <= 0:
            return []
        words = re.findall(r"[A-Za-z0-9\u0980-\u09FF]+", raw)
        terms: list[str] = []
        for w in words:
            if len(w) >= min_word_len:
                terms.append(w)
        terms = list(dict.fromkeys(terms))  # stable unique
        terms.sort(key=len, reverse=True)
        terms = terms[:6]
        if not terms and len(raw) >= 6:
            terms = [raw[:120]]
        if not terms:
            return []
        conds = [Message.content.ilike(f"%{t}%") for t in terms]
        statement: Select[tuple[Message]] = (
            select(Message)
            .join(Session, Message.session_id == Session.id)
            .where(Session.user_id == user_id, or_(*conds))
            .order_by(desc(Message.created_at))
            .limit(limit)
        )
        result = await self.db_session.execute(statement)
        return list(result.scalars().all())

    async def get_usage_summary(self, user_id: str) -> dict[str, int]:
        statement = (
            select(
                func.count(Message.id),
                func.coalesce(func.sum(Message.token_count), 0),
                func.coalesce(
                    func.sum(case((Message.role == "assistant", 1), else_=0)),
                    0,
                ),
            )
            .join(Session, Message.session_id == Session.id)
            .where(Session.user_id == user_id)
        )
        result = await self.db_session.execute(statement)
        total_messages, total_tokens, assistant_messages = result.one()
        return {
            "total_messages": int(total_messages or 0),
            "assistant_messages": int(assistant_messages or 0),
            "total_tokens": int(total_tokens or 0),
        }

    async def fetch_tool_activity(
        self,
        *,
        session_id: str | None = None,
        limit: int = 20,
    ) -> list[Message]:
        statement: Select[tuple[Message]] = (
            select(Message)
            .where(Message.tool_name.is_not(None))
            .order_by(desc(Message.created_at))
            .limit(limit)
        )
        if session_id:
            statement = statement.where(Message.session_id == session_id)
        result = await self.db_session.execute(statement)
        return result.scalars().all()

    async def get_user_profile(self, user_id: str) -> dict[str, Any]:
        key = f"user_profile:{user_id}"
        statement: Select[tuple[Metadata]] = (
            select(Metadata)
            .where(Metadata.key == key)
            .order_by(desc(Metadata.created_at))
            .limit(1)
        )
        result = await self.db_session.execute(statement)
        entry = result.scalars().first()
        if entry is None:
            return {}
        try:
            return json.loads(entry.value)
        except json.JSONDecodeError:
            return {}

    async def upsert_user_profile(self, user_id: str, profile: dict[str, Any]) -> dict[str, Any]:
        key = f"user_profile:{user_id}"
        statement: Select[tuple[Metadata]] = (
            select(Metadata)
            .where(Metadata.key == key)
            .order_by(desc(Metadata.created_at))
            .limit(1)
        )
        result = await self.db_session.execute(statement)
        entry = result.scalars().first()
        existing: dict[str, Any] = {}
        if entry is not None:
            try:
                existing = json.loads(entry.value)
            except json.JSONDecodeError:
                existing = {}
        merged = {**existing, **profile}
        payload = json.dumps(merged, ensure_ascii=True)
        if entry is None:
            entry = Metadata(
                key=key,
                value=payload,
                value_type="json",
            )
            self.db_session.add(entry)
        else:
            entry.value = payload
            entry.value_type = "json"
        await self.db_session.commit()
        return merged

    async def set_message_feedback(self, message_id: str, value: str) -> str | None:
        message = await self.db_session.get(Message, message_id)
        if message is None:
            return None

        key = f"message_feedback:{message_id}"
        statement: Select[tuple[Metadata]] = (
            select(Metadata)
            .where(Metadata.key == key)
            .order_by(desc(Metadata.created_at))
            .limit(1)
        )
        result = await self.db_session.execute(statement)
        entry = result.scalars().first()
        if entry is None:
            entry = Metadata(
                session_id=message.session_id,
                message_id=message_id,
                key=key,
                value=value,
                value_type="text",
            )
            self.db_session.add(entry)
        else:
            entry.value = value
            entry.value_type = "text"
        await self.db_session.commit()
        return value

    async def get_message_feedback(self, message_id: str) -> str | None:
        key = f"message_feedback:{message_id}"
        statement: Select[tuple[Metadata]] = (
            select(Metadata)
            .where(Metadata.key == key)
            .order_by(desc(Metadata.created_at))
            .limit(1)
        )
        result = await self.db_session.execute(statement)
        entry = result.scalars().first()
        return entry.value if entry is not None else None

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
        memory_top_k_cap: int | None = None,
    ) -> list[Message]:
        """Deduplicate and cap semantic memory before prompt injection."""
        if not long_term_messages:
            return []

        cap = memory_top_k_cap if memory_top_k_cap is not None else settings.memory_top_k
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
            if len(deduped) >= cap:
                break
        return deduped
