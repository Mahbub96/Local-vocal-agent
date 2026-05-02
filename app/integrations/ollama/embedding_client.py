from __future__ import annotations

import asyncio
import httpx

from app.core.settings import get_settings


settings = get_settings()


class OllamaEmbeddingClient:
    """Thin async client for local Ollama embedding generation (reuses one HTTP connection pool)."""

    def __init__(
        self,
        *,
        base_url: str | None = None,
        model: str | None = None,
        timeout: int | None = None,
    ) -> None:
        self.base_url = (base_url or settings.ollama_base_url).rstrip("/")
        self.model = model or settings.embedding_model
        self.timeout = timeout or settings.ollama_request_timeout
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(self.timeout),
            limits=httpx.Limits(max_keepalive_connections=32, max_connections=64),
        )

    async def embed_text(self, text: str) -> list[float]:
        payload = {"model": self.model, "input": text}
        attempts = max(1, settings.ollama_retry_attempts)
        for attempt in range(attempts):
            try:
                response = await self._client.post("/api/embed", json=payload)
                response.raise_for_status()
                data = response.json()
                embeddings = data.get("embeddings") or []
                if not embeddings:
                    raise ValueError("Ollama embedding response did not contain embeddings.")
                return embeddings[0]
            except (httpx.TimeoutException, httpx.ConnectError, httpx.ReadError):
                if attempt == attempts - 1:
                    raise
                delay = settings.ollama_retry_base_delay * (2**attempt)
                await asyncio.sleep(delay)
