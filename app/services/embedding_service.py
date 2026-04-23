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
        normalized_query = self._normalize_text(query)
        return await self.embedding_client.embed_text(normalized_query)

    async def index_message(
        self,
        message: Message,
        *,
        source: str = "chat",
        extra_metadata: dict[str, Any] | None = None,
        user_id: str | None = None,
    ) -> None:
        document = self._build_document(message)
        if not document:
            return
        embedding = await self.embedding_client.embed_text(document)
        metadata: dict[str, Any] = {
            "message_id": message.id,
            "session_id": message.session_id,
            "role": message.role,
            "created_at": message.created_at.isoformat() if message.created_at else None,
            "sequence_number": message.sequence_number,
            "content_type": message.content_type,
            "source": source,
            "has_tool_usage": bool(message.tool_name),
            "tool_name": message.tool_name,
            "topic": self._infer_topic(message.content),
        }
        if extra_metadata:
            metadata.update(extra_metadata)
        if user_id:
            metadata["user_id"] = str(user_id)

        self.collection.upsert(
            ids=[message.id],
            documents=[document],
            embeddings=[embedding],
            metadatas=[metadata],
        )

    def _build_document(self, message: Message) -> str:
        normalized_content = self._normalize_text(message.content)
        if not normalized_content:
            return ""
        return "\n".join(
            [
                f"Session: {message.session_id}",
                f"Role: {message.role}",
                f"Message: {normalized_content}",
            ]
        )

    def _normalize_text(self, text: str) -> str:
        # Keep embeddings stable by trimming noisy whitespace.
        return " ".join(text.strip().split())

    def _infer_topic(self, text: str, *, max_words: int = 6) -> str:
        normalized = self._normalize_text(text)
        if not normalized:
            return "general"
        words = normalized.split(" ")
        return " ".join(words[:max_words]).lower()
