from __future__ import annotations

import asyncio
import logging
from pathlib import Path
import re
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.assistant_agent import AssistantAgent
from app.memory.long_term.retriever import LongTermMemoryRetriever
from app.schemas.chat import ChatResponse
from app.services.embedding_service import EmbeddingService
from app.services.memory_service import MemoryService
from app.integrations.tts.coqui_tts import CoquiTTSService
from app.core.settings import get_settings


logger = logging.getLogger(__name__)
settings = get_settings()


class ChatService:
    """Coordinates chat persistence, memory retrieval, and agent execution."""

    def __init__(
        self,
        db_session: AsyncSession,
        *,
        embedding_service: EmbeddingService | None = None,
        tts_service: CoquiTTSService | None = None,
    ) -> None:
        self.db_session = db_session
        self.memory_service = MemoryService(db_session)
        self.embedding_service = embedding_service or EmbeddingService()
        self.retriever = LongTermMemoryRetriever(
            embedding_service=self.embedding_service,
            memory_service=self.memory_service,
        )
        self.agent = AssistantAgent(retriever=self.retriever)
        self.tts_service = tts_service or CoquiTTSService()

    async def handle_chat(
        self,
        *,
        message: str,
        session_id: str | None = None,
        user_id: str | None = None,
        include_tts: bool = False,
        defer_tts: bool = False,
    ) -> ChatResponse:
        normalized_message = self._prepare_message(message)
        if not normalized_message:
            raise ValueError("Message cannot be empty.")

        session = await self.memory_service.get_or_create_session(
            session_id=session_id,
            user_id=user_id,
        )
        user_message = await self.memory_service.add_message(
            session.id,
            role="user",
            content=normalized_message,
        )

        try:
            semantic_matches = await self.retriever.search(
                normalized_message,
                session_id=session.id,
            )
        except Exception as exc:
            logger.exception("Semantic retrieval failed; continuing without long-term memory: %s", exc)
            semantic_matches = []
        memory_context = await self.memory_service.build_context(
            session.id,
            long_term_messages=[match.message for match in semantic_matches],
        )

        agent_result = await self.agent.run(query=normalized_message, memory_context=memory_context)
        assistant_message = await self.memory_service.add_message(
            session.id,
            role="assistant",
            content=str(agent_result["response"]),
            parent_message_id=user_message.id,
            tool_name="internet_search_tool"
            if bool(agent_result.get("used_internet"))
            else "memory_context_tool",
            tool_output=str(agent_result.get("tool_result", "")),
        )

        self._schedule_background_task(
            self.embedding_service.index_message(user_message, source="chat")
        )
        self._schedule_background_task(
            self.embedding_service.index_message(assistant_message, source="chat")
        )

        audio_path: Path | None = None
        if include_tts:
            audio_path = self.tts_service.build_output_path(file_stem=assistant_message.id)
            if defer_tts:
                self._schedule_background_task(
                    self.tts_service.synthesize_to_file(
                        str(agent_result["response"]),
                        file_stem=assistant_message.id,
                    )
                )
            else:
                audio_path = await self.tts_service.synthesize_to_file(
                    str(agent_result["response"]),
                    file_stem=assistant_message.id,
                )

        return ChatResponse(
            session_id=session.id,
            user_message_id=user_message.id,
            assistant_message_id=assistant_message.id,
            response=str(agent_result["response"]),
            used_memory=bool(agent_result["used_memory"]),
            used_internet=bool(agent_result["used_internet"]),
            audio_path=str(audio_path) if audio_path else None,
        )

    def _prepare_message(self, message: str) -> str:
        text = message.strip()
        if not text:
            return ""

        if len(text) > settings.chat_max_input_chars:
            text = self._compact_large_input(text, settings.chat_max_input_chars)
        return " ".join(text.split())

    def _compact_large_input(self, text: str, limit: int) -> str:
        # LaTeX payloads can be very long and command-heavy; extract readable parts.
        if "\\documentclass" in text or text.count("\\") >= 20:
            extracted = re.findall(r"\{([^{}]+)\}", text)
            compact = " ".join(chunk.strip() for chunk in extracted if chunk.strip())
            if compact:
                text = compact
        return text[:limit]

    def _schedule_background_task(self, coroutine: Any) -> None:
        task = asyncio.create_task(coroutine)
        task.add_done_callback(self._log_background_task_error)

    def _log_background_task_error(self, task: asyncio.Task) -> None:
        try:
            task.result()
        except Exception as exc:
            logger.exception("Background task failed: %s", exc)
