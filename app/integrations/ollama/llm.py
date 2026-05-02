from __future__ import annotations

import threading

from langchain_ollama import ChatOllama

from app.core.settings import get_settings
from app.services.effective_assistant_prefs import EffectiveAssistantPrefs


settings = get_settings()


def build_chat_ollama_for_prefs(prefs: EffectiveAssistantPrefs) -> ChatOllama:
    """Per-request Ollama client when user overrides num_ctx / num_predict / temperature."""
    return ChatOllama(
        base_url=settings.ollama_base_url,
        model=settings.ollama_model,
        temperature=prefs.ollama_temperature,
        request_timeout=settings.ollama_request_timeout,
        num_ctx=prefs.ollama_num_ctx,
        num_predict=prefs.ollama_num_predict,
    )


class OllamaChatModel:
    """Factory for the local Ollama chat model used by LangChain."""

    def __init__(self) -> None:
        self._model = ChatOllama(
            base_url=settings.ollama_base_url,
            model=settings.ollama_model,
            temperature=settings.ollama_temperature,
            request_timeout=settings.ollama_request_timeout,
            num_ctx=settings.ollama_num_ctx,
            num_predict=settings.ollama_num_predict,
        )

    @property
    def client(self) -> ChatOllama:
        return self._model


_ollama_chat_singleton: OllamaChatModel | None = None
_ollama_chat_lock = threading.Lock()


def get_ollama_chat_model() -> OllamaChatModel:
    """One LangChain ChatOllama client per process (connection / config reuse)."""
    global _ollama_chat_singleton
    if _ollama_chat_singleton is None:
        with _ollama_chat_lock:
            if _ollama_chat_singleton is None:
                _ollama_chat_singleton = OllamaChatModel()
    return _ollama_chat_singleton
