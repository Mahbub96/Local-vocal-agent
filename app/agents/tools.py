from __future__ import annotations

import json
import logging

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from app.memory.long_term.retriever import LongTermMemoryRetriever
from app.integrations.search.duckduckgo import DuckDuckGoSearchClient

logger = logging.getLogger(__name__)


class MemorySearchInput(BaseModel):
    query: str = Field(..., description="Query used to search past conversations.")
    session_id: str | None = Field(
        default=None, description="Optional session id to limit semantic retrieval."
    )
    top_k: int = Field(default=5, description="Maximum number of similar messages to return.")


class WebSearchInput(BaseModel):
    query: str = Field(..., description="Real-time query that requires internet search.")
    max_results: int = Field(default=5, description="Maximum number of search results.")


def build_memory_search_tool(retriever: LongTermMemoryRetriever) -> StructuredTool:
    async def _memory_search(query: str, session_id: str | None = None, top_k: int = 5) -> str:
        safe_top_k = max(1, min(top_k, 20))
        try:
            matches = await retriever.search(query, top_k=safe_top_k, session_id=session_id)
        except Exception as exc:
            logger.exception("Memory search tool failed: %s", exc)
            return json.dumps([], ensure_ascii=True)
        payload = [
            {
                "message_id": match.message.id,
                "session_id": match.message.session_id,
                "role": match.message.role,
                "content": match.message.content,
                "score": match.score,
                "created_at": match.message.created_at.isoformat()
                if match.message.created_at
                else None,
            }
            for match in matches
        ]
        return json.dumps(payload, ensure_ascii=True)

    return StructuredTool.from_function(
        coroutine=_memory_search,
        name="memory_search_tool",
        description="Search semantically similar past conversation snippets from local memory.",
        args_schema=MemorySearchInput,
    )


def build_web_search_tool(search_client: DuckDuckGoSearchClient) -> StructuredTool:
    async def _web_search(query: str, max_results: int = 5) -> str:
        safe_max_results = max(1, min(max_results, 10))
        try:
            results = await search_client.search(query, max_results=safe_max_results)
        except Exception as exc:
            logger.exception("Internet search tool failed: %s", exc)
            return json.dumps([], ensure_ascii=True)
        return json.dumps(results, ensure_ascii=True)

    return StructuredTool.from_function(
        coroutine=_web_search,
        name="internet_search_tool",
        description="Search the internet for current or real-time information.",
        args_schema=WebSearchInput,
    )
