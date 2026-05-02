from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from pathlib import Path
import re
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.assistant_agent import AssistantAgent, ModelUnavailableError
from app.memory.long_term.retriever import LongTermMemoryRetriever
from app.schemas.chat import ChatResponse
from app.services.embedding_service import EmbeddingService
from app.services.memory_service import MemoryService
from app.integrations.tts.coqui_tts import CoquiTTSService
from app.integrations.tts.tts_locale import prefers_bangla_tts
from app.core.settings import get_settings


logger = logging.getLogger(__name__)
settings = get_settings()

# Widen vector recall for "who am I" / "my name" so prior self-intro messages still rank.
_IDENTITY_RETRIEVAL = re.compile(
    r"(?i)(my name|what(?:'s| is) my name|who am i\b|"
    r"do you know my name|remind me.*\bname\b|call me|i(?:'m| am)\b.*name)"
)


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
        self._tts_default = tts_service or CoquiTTSService()
        self._tts_bn: CoquiTTSService | None = None

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
        effective_user_id = (user_id or session.user_id) or None
        user_message = await self.memory_service.add_message(
            session.id,
            role="user",
            content=normalized_message,
        )

        retrieval_query = normalized_message
        if effective_user_id and _IDENTITY_RETRIEVAL.search(normalized_message):
            retrieval_query = (
                f"{normalized_message}\n"
                f"name identity self-introduction who I am user profile preferences"
            )
        try:
            semantic_matches = await self.retriever.search(
                retrieval_query,
                session_id=session.id,
                user_id=effective_user_id,
            )
        except Exception as exc:
            logger.exception("Semantic retrieval failed; continuing without long-term memory: %s", exc)
            semantic_matches = []
        memory_context = await self.memory_service.build_context(
            session.id,
            long_term_messages=[match.message for match in semantic_matches],
            user_id=effective_user_id,
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
            self.embedding_service.index_message(
                user_message, source="chat", user_id=effective_user_id
            )
        )
        self._schedule_background_task(
            self.embedding_service.index_message(
                assistant_message, source="chat", user_id=effective_user_id
            )
        )

        audio_path: Path | None = None
        if include_tts:
            reply_text = str(agent_result["response"])
            tts_svc = await self._tts_for_profile(effective_user_id)
            if defer_tts:
                # Fire-and-forget: path may appear later; failures are logged only.
                self._schedule_background_task(
                    self._tts_deferred(reply_text, assistant_message.id, tts_svc)
                )
                audio_path = tts_svc.build_output_path(file_stem=assistant_message.id)
            else:
                path = await tts_svc.synthesize_to_file(reply_text, file_stem=assistant_message.id)
                audio_path = path

        return ChatResponse(
            session_id=session.id,
            user_message_id=user_message.id,
            assistant_message_id=assistant_message.id,
            response=str(agent_result["response"]),
            used_memory=bool(agent_result["used_memory"]),
            used_internet=bool(agent_result["used_internet"]),
            audio_path=str(audio_path) if audio_path else None,
        )

    async def handle_chat_stream(
        self,
        *,
        message: str,
        session_id: str | None = None,
        user_id: str | None = None,
    ) -> AsyncIterator[str]:
        """SSE lines: `token` deltas, then `done` with ChatResponse JSON."""
        try:
            normalized_message = self._prepare_message(message)
            if not normalized_message:
                yield f"event: error\ndata: {json.dumps({'detail': 'Message cannot be empty.'})}\n\n"
                return

            session = await self.memory_service.get_or_create_session(
                session_id=session_id,
                user_id=user_id,
            )
            effective_user_id = (user_id or session.user_id) or None
            user_message = await self.memory_service.add_message(
                session.id,
                role="user",
                content=normalized_message,
            )

            retrieval_query = normalized_message
            if effective_user_id and _IDENTITY_RETRIEVAL.search(normalized_message):
                retrieval_query = (
                    f"{normalized_message}\n"
                    f"name identity self-introduction who I am user profile preferences"
                )
            try:
                semantic_matches = await self.retriever.search(
                    retrieval_query,
                    session_id=session.id,
                    user_id=effective_user_id,
                )
            except Exception as exc:
                logger.exception("Semantic retrieval failed; continuing without long-term memory: %s", exc)
                semantic_matches = []
            memory_context = await self.memory_service.build_context(
                session.id,
                long_term_messages=[match.message for match in semantic_matches],
                user_id=effective_user_id,
            )

            agent_result: dict[str, object] | None = None
            try:
                async for item in self.agent.stream_run(
                    query=normalized_message,
                    memory_context=memory_context,
                ):
                    if isinstance(item, str):
                        yield f"event: token\ndata: {json.dumps({'t': item})}\n\n"
                    else:
                        agent_result = item
            except ModelUnavailableError as exc:
                yield f"event: error\ndata: {json.dumps({'detail': str(exc)})}\n\n"
                return

            if agent_result is None:
                yield f"event: error\ndata: {json.dumps({'detail': 'Stream ended without response.'})}\n\n"
                return

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
                self.embedding_service.index_message(
                    user_message, source="chat", user_id=effective_user_id
                )
            )
            self._schedule_background_task(
                self.embedding_service.index_message(
                    assistant_message, source="chat", user_id=effective_user_id
                )
            )

            payload = ChatResponse(
                session_id=session.id,
                user_message_id=user_message.id,
                assistant_message_id=assistant_message.id,
                response=str(agent_result["response"]),
                used_memory=bool(agent_result["used_memory"]),
                used_internet=bool(agent_result["used_internet"]),
                audio_path=None,
            )
            yield f"event: done\ndata: {json.dumps(payload.model_dump())}\n\n"
        except Exception as exc:
            logger.exception("chat stream failed: %s", exc)
            yield f"event: error\ndata: {json.dumps({'detail': str(exc)})}\n\n"

    async def _tts_deferred(self, reply_text: str, file_stem: str, tts: CoquiTTSService) -> None:
        path = await tts.synthesize_to_file(reply_text, file_stem=file_stem)
        if path is None:
            logger.warning("Deferred TTS produced no audio (stem=%s)", file_stem)

    async def _tts_for_profile(self, effective_user_id: str | None) -> CoquiTTSService:
        """English (default) model unless profile language is Bangla and bn model is configured."""
        if not effective_user_id:
            return self._tts_default
        profile = await self.memory_service.get_user_profile(effective_user_id)
        lang = profile.get("language") if profile else None
        if not isinstance(lang, str) or not prefers_bangla_tts(lang):
            return self._tts_default
        bn_name = (settings.tts_model_name_bn or "").strip()
        if not bn_name:
            logger.warning(
                "Profile language is Bangla but TTS_MODEL_NAME_BN is empty; using default TTS model"
            )
            return self._tts_default
        if self._tts_bn is None:
            self._tts_bn = CoquiTTSService(model_name=bn_name)
        return self._tts_bn

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
