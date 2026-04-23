from __future__ import annotations

import json
import logging
import re

from app.core.settings import get_settings
from app.integrations.ollama.llm import OllamaChatModel
from app.integrations.search.duckduckgo import DuckDuckGoSearchClient
from app.memory.long_term.retriever import LongTermMemoryRetriever
from app.services.memory_service import MemoryContext


settings = get_settings()
logger = logging.getLogger(__name__)

REALTIME_PATTERN = re.compile(
    r"\b(weather|news|latest|today|current|now|stock|price|forecast|headline|recent)\b",
    re.IGNORECASE,
)


class AssistantAgent:
    """Local assistant orchestration with deterministic tool routing."""

    def __init__(
        self,
        *,
        retriever: LongTermMemoryRetriever,
        search_client: DuckDuckGoSearchClient | None = None,
        llm: OllamaChatModel | None = None,
    ) -> None:
        self.retriever = retriever
        self.search_client = search_client or DuckDuckGoSearchClient()
        self.llm = (llm or OllamaChatModel()).client

    def needs_internet_search(self, query: str) -> bool:
        return bool(REALTIME_PATTERN.search(query))

    async def run(self, *, query: str, memory_context: MemoryContext) -> dict[str, object]:
        use_search = self.needs_internet_search(query)

        long_term_context = "\n".join(
            f"[{msg.role}] {msg.content}" for msg in memory_context.long_term_messages
        ) or "No semantically relevant memory retrieved."
        short_term_context = "\n".join(
            f"[{msg['role']}] {msg['content']}" for msg in memory_context.short_term_messages
        ) or "No recent conversation context."
        web_context = "No internet search was used."
        tool_trace_payload: list[dict[str, object]] = []

        if use_search:
            try:
                web_results = await self.search_client.search(query)
            except Exception as exc:
                logger.exception("Internet search failed; continuing without web context: %s", exc)
                web_results = []

            if web_results:
                web_context = "\n".join(
                    f"- {item.get('title', '')}: {item.get('body', '')} ({item.get('href', '')})"
                    for item in web_results[: settings.duckduckgo_max_results]
                )
            tool_trace_payload.append(
                {
                    "tool": "internet_search_tool",
                    "used": True,
                    "results": len(web_results),
                }
            )

        prompt = (
            "You are a local AI assistant.\n"
            "Use local memory for historical context.\n"
            "Use internet context only when provided.\n"
            "If internet context is unavailable, say you may be missing real-time freshness.\n"
            "Keep answers grounded, concise, and practical.\n\n"
            f"Recent conversation:\n{short_term_context}\n\n"
            f"Retrieved long-term memory:\n{long_term_context}\n\n"
            f"Internet context:\n{web_context}\n\n"
            f"User query:\n{query}"
        )
        try:
            result = await self.llm.ainvoke(prompt)
            response_text = str(getattr(result, "content", result)).strip()
            if not response_text:
                raise ValueError("Model produced an empty output.")
            tool_trace = json.dumps(tool_trace_payload, default=str)
        except Exception as exc:
            logger.exception("LLM execution failed; applying minimal fallback prompt: %s", exc)
            fallback_result = await self.llm.ainvoke(query)
            response_text = str(getattr(fallback_result, "content", fallback_result)).strip()
            if not response_text:
                response_text = (
                    "I encountered a temporary issue while processing your request. "
                    "Please try again."
                )
            tool_trace = json.dumps([], default=str)
        return {
            "response": response_text,
            "used_internet": use_search,
            "used_memory": True,
            "tool_result": tool_trace,
        }
