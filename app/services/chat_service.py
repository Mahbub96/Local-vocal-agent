from __future__ import annotations

import asyncio
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.assistant_agent import AssistantAgent
from app.memory.long_term.retriever import LongTermMemoryRetriever
from app.schemas.chat import ChatResponse
from app.services.embedding_service import EmbeddingService
from app.services.memory_service import MemoryService
from app.integrations.tts.coqui_tts import CoquiTTSService


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
        session = await self.memory_service.get_or_create_session(
            session_id=session_id,
            user_id=user_id,
        )
        user_message = await self.memory_service.add_message(
            session.id,
            role="user",
            content=message,
        )

        semantic_matches = await self.retriever.search(message, session_id=session.id)
        memory_context = await self.memory_service.build_context(
            session.id,
            long_term_messages=[match.message for match in semantic_matches],
        )

        agent_result = await self.agent.run(query=message, memory_context=memory_context)
        assistant_message = await self.memory_service.add_message(
            session.id,
            role="assistant",
            content=str(agent_result["response"]),
            parent_message_id=user_message.id,
        )

        asyncio.create_task(self.embedding_service.index_message(user_message, source="chat"))
        asyncio.create_task(
            self.embedding_service.index_message(assistant_message, source="chat")
        )

        audio_path: Path | None = None
        if include_tts:
            audio_path = self.tts_service.build_output_path(file_stem=assistant_message.id)
            if defer_tts:
                asyncio.create_task(
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
