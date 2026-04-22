from __future__ import annotations

from langchain_ollama import ChatOllama

from app.core.settings import get_settings


settings = get_settings()


class OllamaChatModel:
    """Factory for the local Ollama chat model used by LangChain."""

    def __init__(self) -> None:
        self._model = ChatOllama(
            base_url=settings.ollama_base_url,
            model=settings.ollama_model,
            temperature=0.2,
            request_timeout=settings.ollama_request_timeout,
        )

    @property
    def client(self) -> ChatOllama:
        return self._model
