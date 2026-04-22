from __future__ import annotations

from typing import Any

from app.database.chroma.client import get_memory_collection
from app.integrations.ollama.embedding_client import OllamaEmbeddingClient
from app.models import Message


class EmbeddingService:
    """Handles embedding generation plus Chroma indexing and retrieval prep."""

    def __init__(self, embedding_client: OllamaEmbeddingClient | None = None) -> None:
        self.embedding_client = embedding_client or OllamaEmbeddingClient()
        self.collection = get_memory_collection()

    async def embed_query(self, query: str) -> list[float]:
        return await self.embedding_client.embed_text(query.strip())

    async def index_message(
        self,
        message: Message,
        *,
        source: str = "chat",
        extra_metadata: dict[str, Any] | None = None,
    ) -> None:
        document = self._build_document(message)
        embedding = await self.embedding_client.embed_text(document)
        metadata = {
            "message_id": message.id,
            "session_id": message.session_id,
            "role": message.role,
            "created_at": message.created_at.isoformat() if message.created_at else None,
            "sequence_number": message.sequence_number,
            "content_type": message.content_type,
            "source": source,
            "has_tool_usage": bool(message.tool_name),
            "tool_name": message.tool_name,
        }
        if extra_metadata:
            metadata.update(extra_metadata)

        self.collection.upsert(
            ids=[message.id],
            documents=[document],
            embeddings=[embedding],
            metadatas=[metadata],
        )

    def _build_document(self, message: Message) -> str:
        return "\n".join(
            [
                f"Session: {message.session_id}",
                f"Role: {message.role}",
                f"Message: {message.content}",
            ]
        )
