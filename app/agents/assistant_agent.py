from __future__ import annotations

import json
import logging
import re

from app.core.settings import get_settings
from app.integrations.ollama.llm import OllamaChatModel
from app.integrations.search.duckduckgo import DuckDuckGoSearchClient
from app.integrations.time.world_time import (
    extract_iso_clock_from_time_line,
    fetch_local_time_utc_string,
    refine_search_query_for_tool,
    resolve_timezone_for_query,
)
from app.memory.long_term.retriever import LongTermMemoryRetriever
from app.services.memory_service import MemoryContext


settings = get_settings()
logger = logging.getLogger(__name__)

# Triggers a DuckDuckGo pull (and/or live clock below). User saying "search" should always run.
EXPLICIT_SEARCH = re.compile(r"\bsearch\b", re.IGNORECASE)
REALTIME_PATTERN = re.compile(
    r"\b(weather|news|latest|today|current|now|stock|price|forecast|"
    r"headline|recent|time|timezone|clock|lookup|online|live)\b",
    re.IGNORECASE,
)


# Short greetings / acknowledgements — do not hit the web when memory is empty.
_TRIVIAL_UTTERANCE = re.compile(
    r"^\s*(hi|hello|hey|yo|ok|okay|thanks?|thank you|bye|goodbye|no|yes|sure|"
    r"lol|haha|ha|nice|great|cool|yep|nope|what\?*)\s*[\s!.?…]*$",
    re.IGNORECASE,
)


def _is_trivial_utterance(query: str) -> bool:
    t = query.strip()
    if len(t) < 2:
        return True
    if len(t) <= 64 and _TRIVIAL_UTTERANCE.match(t):
        return True
    return False


def _has_semantic_long_term_hits(memory_context: MemoryContext) -> bool:
    return len(memory_context.long_term_messages) > 0


def _internet_context_blocks(
    time_line: str | None,
    web_results: list[dict[str, str]],
) -> list[str]:
    blocks: list[str] = []
    if time_line:
        blocks.append(
            "LIVE TIME (use this exact wall-clock in your answer; do not use placeholders): "
            + time_line
        )
    if web_results:
        blocks.append(
            "Web search snippets:\n"
            + "\n".join(
                f"- {item.get('title', '')}: {item.get('body', '')} ({item.get('href', '')})"
                for item in web_results[: settings.duckduckgo_max_results]
            )
        )
    elif not time_line:
        blocks.append(
            "Web search did not return usable text snippets. "
            "Use recent conversation and long-term memory when present; state uncertainty if needed."
        )
    return blocks


# Models sometimes echo training-style templates; strip even when a live time was provided.
_LLM_TIME_PLACEHOLDER = re.compile(
    r"\[?\s*insert (?:the )?current time here\s*\]?|"
    r"\[insert[^\]\n]{0,60}time[^\]\n]{0,30}here\s*\]|"
    r"\[TBD\]",
    re.IGNORECASE,
)


def _user_profile_block(profile: dict | None) -> str:
    if not profile:
        return ""
    parts: list[str] = []
    for key, label in (
        ("name", "Name"),
        ("language", "Language"),
        ("location", "Location"),
        ("profession", "Profession"),
        ("project", "Project"),
    ):
        v = profile.get(key)
        if isinstance(v, str) and v.strip():
            parts.append(f"- {label}: {v.strip()}")
    prefs = profile.get("preferences")
    if isinstance(prefs, list) and prefs:
        parts.append(f"- Preferences: {', '.join(str(p) for p in prefs if p)}")
    if not parts:
        return ""
    return (
        "Saved user profile (authoritative for this user; if a name is listed, use it when they ask their name; "
        "do not claim you have no access to their name if it is shown here):\n"
        + "\n".join(parts)
        + "\n\n"
    )


def _strip_llm_time_placeholders(response: str, time_line: str | None) -> str:
    if time_line:
        clock = extract_iso_clock_from_time_line(time_line) or time_line
        return _LLM_TIME_PLACEHOLDER.sub(clock, response).strip()
    return _LLM_TIME_PLACEHOLDER.sub(
        "a live time service was unreachable—Bangladesh (Asia/Dhaka) is UTC+6 (year-round)",
        response,
    ).strip()


def should_use_internet_search(
    query: str,
    memory_context: MemoryContext,
    *,
    zone: str | None,
) -> bool:
    """Prefer memory; pull web when there is no semantic hit, or the query clearly needs fresh/online data."""
    if zone is not None:
        return True
    if EXPLICIT_SEARCH.search(query):
        return True
    if REALTIME_PATTERN.search(query):
        return True
    if _is_trivial_utterance(query):
        return False
    if settings.assistant_search_if_no_memory and not _has_semantic_long_term_hits(memory_context):
        return True
    return False


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

    async def run(self, *, query: str, memory_context: MemoryContext) -> dict[str, object]:
        zone = resolve_timezone_for_query(query)
        time_line: str | None = None
        if zone:
            time_line = await fetch_local_time_utc_string(zone)

        use_search = should_use_internet_search(query, memory_context, zone=zone)

        profile_text = _user_profile_block(memory_context.user_profile)
        long_term_context = "\n".join(
            f"[{msg.role}] {msg.content}" for msg in memory_context.long_term_messages
        ) or "No semantically relevant memory retrieved."
        short_term_context = "\n".join(
            f"[{msg['role']}] {msg['content']}" for msg in memory_context.short_term_messages
        ) or "No recent conversation context."
        web_context = "No internet search was used."
        tool_trace_payload: list[dict[str, object]] = []

        web_results: list[dict[str, str]] = []
        if use_search:
            search_q = refine_search_query_for_tool(query)
            try:
                web_results = await self.search_client.search(search_q)
            except Exception as exc:
                logger.exception("Internet search failed; continuing without web context: %s", exc)
                web_results = []

            context_blocks = _internet_context_blocks(time_line, web_results)
            if context_blocks:
                web_context = "\n\n".join(context_blocks)
            tool_trace_payload.append(
                {
                    "tool": "internet_search_tool",
                    "used": True,
                    "results": len(web_results),
                    "time_zone": zone,
                    "used_live_clock": time_line is not None,
                }
            )

        prompt = (
            "You are a personal local assistant with long-term memory, short-term context, and optional web search.\n"
            "Answer from long-term and recent conversation when they are enough.\n"
            "When a LIVE TIME line is present, copy the exact YYYY-MM-DD HH:MM:SS from it into your answer.\n"
            "FORBIDDEN: the phrase 'insert' near 'time' and 'here', bracket templates, TBD, or [placeholder] for time.\n"
            "When web snippets or LIVE TIME are provided, use them for facts; do not invent times.\n"
            "If web has no snippets and memory is thin, you may use general knowledge and say you could not verify online.\n\n"
            f"{profile_text}"
            f"Recent conversation:\n{short_term_context}\n\n"
            f"Retrieved long-term memory (semantic search):\n{long_term_context}\n\n"
            f"Internet / live data (may be empty):\n{web_context}\n\n"
            f"User query:\n{query}"
        )
        try:
            result = await self.llm.ainvoke(prompt)
            response_text = str(getattr(result, "content", result)).strip()
            if not response_text:
                raise ValueError("Model produced an empty output.")
            response_text = _strip_llm_time_placeholders(response_text, time_line)
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
            else:
                response_text = _strip_llm_time_placeholders(response_text, time_line)
            tool_trace = json.dumps([], default=str)
        return {
            "response": response_text,
            "used_internet": use_search,
            "used_memory": True,
            "tool_result": tool_trace,
        }
