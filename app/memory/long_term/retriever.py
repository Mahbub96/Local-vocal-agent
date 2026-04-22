from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.core.settings import get_settings
from app.database.chroma.client import get_memory_collection
from app.models import Message
from app.services.embedding_service import EmbeddingService
from app.services.memory_service import MemoryService


settings = get_settings()


@dataclass(slots=True)
class SemanticMemoryMatch:
    """Structured semantic search result hydrated from SQLite."""

    message: Message
    score: float
    metadata: dict[str, Any]


class LongTermMemoryRetriever:
    """Coordinates Chroma similarity search with SQLite hydration."""

    def __init__(
        self,
        *,
        embedding_service: EmbeddingService,
        memory_service: MemoryService,
    ) -> None:
        self.embedding_service = embedding_service
        self.memory_service = memory_service
        self.collection = get_memory_collection()

    async def search(
        self,
        query: str,
        *,
        top_k: int | None = None,
        session_id: str | None = None,
    ) -> list[SemanticMemoryMatch]:
        query_embedding = await self.embedding_service.embed_query(query)
        query_filter = {"session_id": session_id} if session_id else None
        result = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k or settings.memory_top_k,
            where=query_filter,
            include=["metadatas", "distances"],
        )

        ids = result.get("ids", [[]])[0]
        distances = result.get("distances", [[]])[0]
        metadatas = result.get("metadatas", [[]])[0]
        messages = await self.memory_service.fetch_messages_by_ids(ids)
        message_by_id = {message.id: message for message in messages}

        matches: list[SemanticMemoryMatch] = []
        for message_id, distance, metadata in zip(ids, distances, metadatas, strict=False):
            message = message_by_id.get(message_id)
            if message is None:
                continue
            matches.append(
                SemanticMemoryMatch(
                    message=message,
                    score=float(distance),
                    metadata=metadata or {},
                )
            )
        return matches
