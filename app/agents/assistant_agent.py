from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from urllib.parse import quote

import httpx

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


class ModelUnavailableError(RuntimeError):
    """Raised when configured Ollama model is missing/unavailable."""


def _is_model_not_found_error(exc: Exception) -> bool:
    text = str(exc).lower()
    if "model" in text and "not found" in text:
        return True
    cause = getattr(exc, "__cause__", None)
    if isinstance(cause, Exception):
        return _is_model_not_found_error(cause)
    context = getattr(exc, "__context__", None)
    if isinstance(context, Exception):
        return _is_model_not_found_error(context)
    return False

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

_WEATHER_QUERY = re.compile(
    r"(?i)\b(weather|temperature|forecast|rain|raining|humidity|wind| আবহাওয়া|তাপমাত্রা)\b"
)
_TIME_QUERY = re.compile(
    r"(?i)\b(time|clock|timezone|what time|current time|local time|সময়|টাইম)\b"
)
_DATE_QUERY = re.compile(
    r"(?i)\b(date|today(?:'s|s)? date|today|current date|আজ(?:কের)?\s*তারিখ|তারিখ)\b"
)
_INTERNET_ACCESS_QUERY = re.compile(
    r"(?i)(\b(internet|online|web|browse|connection|network)\b.*\b(have|can|access|connected|working)\b|"
    r"\bdo you have internet\b|"
    r"\bare you online\b|"
    r"\bcan you browse\b)"
)


def _is_trivial_utterance(query: str) -> bool:
    t = query.strip()
    if len(t) < 2:
        return True
    if len(t) <= 64 and _TRIVIAL_UTTERANCE.match(t):
        return True
    return False


def _is_weather_query(query: str) -> bool:
    return bool(_WEATHER_QUERY.search(query))


def _is_time_query(query: str) -> bool:
    return bool(_TIME_QUERY.search(query))


def _is_date_query(query: str) -> bool:
    return bool(_DATE_QUERY.search(query))


def _is_internet_access_query(query: str) -> bool:
    return bool(_INTERNET_ACCESS_QUERY.search(query))


def _resolve_timezone_from_profile(profile: dict | None) -> str | None:
    if not profile:
        return None
    location = str(profile.get("location") or "").strip()
    if not location:
        return None
    # Reuse existing timezone resolver by turning location into a time-intent phrase.
    return resolve_timezone_for_query(f"current time in {location}")


def _extract_weather_location(query: str) -> str:
    q = query.strip()
    if re.search(r"(?i)\bdhaka|bangladesh|বাংলাদেশ|ঢাকা\b", q):
        return "Dhaka"
    m = re.search(r"(?i)\b(?:in|for|at)\s+([A-Za-z][A-Za-z\s-]{1,40})", q)
    if m:
        return m.group(1).strip()
    return "Dhaka"


async def _fetch_weather_snapshot(query: str) -> dict[str, str] | None:
    location = _extract_weather_location(query)
    url = f"https://wttr.in/{quote(location)}?format=j1"
    try:
        async with httpx.AsyncClient(timeout=8.0, follow_redirects=True) as client:
            response = await client.get(url)
        if response.status_code != 200:
            return None
        payload = response.json()
    except Exception:
        return None

    current = (payload.get("current_condition") or [{}])[0]
    if not isinstance(current, dict):
        return None
    desc = ""
    desc_list = current.get("weatherDesc") or []
    if isinstance(desc_list, list) and desc_list:
        first = desc_list[0]
        if isinstance(first, dict):
            desc = str(first.get("value", "")).strip()

    temp_c = str(current.get("temp_C", "")).strip()
    feels_c = str(current.get("FeelsLikeC", "")).strip()
    humidity = str(current.get("humidity", "")).strip()
    wind_kmph = str(current.get("windspeedKmph", "")).strip()
    observed = str(current.get("localObsDateTime", "")).strip()
    if not temp_c:
        return None

    summary = (
        f"Current weather in {location}: {desc or 'Condition unavailable'}, "
        f"temperature {temp_c}°C, feels like {feels_c or temp_c}°C, "
        f"humidity {humidity or 'N/A'}%, wind {wind_kmph or 'N/A'} km/h."
    )
    return {
        "location": location,
        "summary": summary,
        "temp_c": temp_c,
        "feels_like_c": feels_c or temp_c,
        "humidity": humidity or "N/A",
        "wind_kmph": wind_kmph or "N/A",
        "condition": desc or "Condition unavailable",
        "observed": observed or "N/A",
    }


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


def _select_weather_web_result(web_results: list[dict[str, str]]) -> dict[str, str] | None:
    if not web_results:
        return None
    score_keys = ("weather", "temperature", "forecast", "rain", "humidity", "wind", "dhaka")
    best: tuple[int, dict[str, str]] | None = None
    for item in web_results:
        hay = f"{item.get('title', '')} {item.get('body', '')}".lower()
        score = sum(1 for key in score_keys if key in hay)
        if best is None or score > best[0]:
            best = (score, item)
    return best[1] if best else web_results[0]


def _compact_time_response(time_line: str | None) -> str | None:
    if not time_line:
        return None
    clock = extract_iso_clock_from_time_line(time_line)
    if not clock:
        return time_line
    zone_match = re.search(r"for ([^:]+):", time_line)
    zone = zone_match.group(1).strip() if zone_match else "your location"
    return f"Current local time in {zone}: {clock}."


def _compact_date_response(time_line: str | None) -> str | None:
    if not time_line:
        return None
    clock = extract_iso_clock_from_time_line(time_line)
    if not clock:
        return None
    try:
        dt = datetime.strptime(clock, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None
    zone_match = re.search(r"for ([^:]+):", time_line)
    zone = zone_match.group(1).strip() if zone_match else "your location"
    return f"Today's date in {zone} is {dt.date().isoformat()}."


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
    if _is_internet_access_query(query):
        return True
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
        if zone is None and (_is_time_query(query) or _is_date_query(query)):
            zone = _resolve_timezone_from_profile(memory_context.user_profile)
        time_line: str | None = None
        weather_snapshot: dict[str, str] | None = None
        if zone:
            time_line = await fetch_local_time_utc_string(zone)
        if _is_weather_query(query):
            weather_snapshot = await _fetch_weather_snapshot(query)

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
            if weather_snapshot:
                context_blocks.insert(
                    0,
                    "LIVE WEATHER (use this as primary weather source): "
                    + weather_snapshot["summary"],
                )
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
            if weather_snapshot:
                tool_trace_payload.append(
                    {
                        "tool": "weather_live_tool",
                        "used": True,
                        "provider": "wttr.in",
                        "location": weather_snapshot["location"],
                    }
                )
        elif weather_snapshot:
            web_context = (
                "LIVE WEATHER (use this as primary weather source): "
                + weather_snapshot["summary"]
            )
            tool_trace_payload.append(
                {
                    "tool": "weather_live_tool",
                    "used": True,
                    "provider": "wttr.in",
                    "location": weather_snapshot["location"],
                }
            )

        if weather_snapshot and _is_weather_query(query):
            tool_trace = json.dumps(tool_trace_payload, default=str)
            return {
                "response": weather_snapshot["summary"],
                "used_internet": True,
                "used_memory": True,
                "tool_result": tool_trace,
            }
        if _is_weather_query(query):
            selected = _select_weather_web_result(web_results)
            if selected:
                title = str(selected.get("title", "")).strip()
                body = str(selected.get("body", "")).strip()
                href = str(selected.get("href", "")).strip()
                line = " ".join(part for part in (title, body) if part).strip()
                if not line:
                    line = "Latest weather details are available from the linked source."
                if href:
                    line = f"{line} Source: {href}"
                tool_trace = json.dumps(tool_trace_payload, default=str)
                return {
                    "response": line,
                    "used_internet": True,
                    "used_memory": True,
                    "tool_result": tool_trace,
                }
            tool_trace = json.dumps(tool_trace_payload, default=str)
            return {
                "response": (
                    "I could not fetch live weather data right now from online sources. "
                    "Please retry in a moment."
                ),
                "used_internet": True,
                "used_memory": True,
                "tool_result": tool_trace,
            }

        if _is_time_query(query):
            tool_trace = json.dumps(tool_trace_payload, default=str)
            compact = _compact_time_response(time_line)
            if compact:
                return {
                    "response": compact,
                    "used_internet": True,
                    "used_memory": True,
                    "tool_result": tool_trace,
                }
            return {
                "response": (
                    "I could not fetch live time right now from online time providers. "
                    "Please retry in a moment."
                ),
                "used_internet": True,
                "used_memory": True,
                "tool_result": tool_trace,
            }

        if _is_date_query(query):
            tool_trace = json.dumps(tool_trace_payload, default=str)
            compact_date = _compact_date_response(time_line)
            if compact_date:
                return {
                    "response": compact_date,
                    "used_internet": True,
                    "used_memory": True,
                    "tool_result": tool_trace,
                }
            return {
                "response": (
                    "I could not fetch today's date from live time providers right now. "
                    "Please retry in a moment."
                ),
                "used_internet": True,
                "used_memory": True,
                "tool_result": tool_trace,
            }

        if _is_internet_access_query(query):
            tool_trace = json.dumps(tool_trace_payload, default=str)
            if web_results:
                return {
                    "response": (
                        "Yes — internet access is currently available. "
                        f"I can fetch live web results (received {len(web_results)} result snippets just now)."
                    ),
                    "used_internet": True,
                    "used_memory": True,
                    "tool_result": tool_trace,
                }
            return {
                "response": (
                    "I could not confirm internet access right now because live web lookup failed. "
                    "Please check network status and try again."
                ),
                "used_internet": True,
                "used_memory": True,
                "tool_result": tool_trace,
            }

        prompt = (
            "You are a personal local assistant with long-term memory, short-term context, and optional web search.\n"
            "Answer from long-term and recent conversation when they are enough.\n"
            "Never claim you have no real-time internet or browsing access when internet/tool context is present.\n"
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
            if _is_model_not_found_error(exc):
                raise ModelUnavailableError(
                    f"Ollama model '{settings.ollama_model}' is not available locally. "
                    f"Pull it first (e.g. `ollama pull {settings.ollama_model}`) or set OLLAMA_MODEL."
                ) from exc
            logger.exception("LLM execution failed; applying minimal fallback prompt: %s", exc)
            try:
                fallback_result = await self.llm.ainvoke(query)
                response_text = str(getattr(fallback_result, "content", fallback_result)).strip()
            except Exception as fallback_exc:
                if _is_model_not_found_error(fallback_exc):
                    raise ModelUnavailableError(
                        f"Ollama model '{settings.ollama_model}' is not available locally. "
                        f"Pull it first (e.g. `ollama pull {settings.ollama_model}`) or set OLLAMA_MODEL."
                    ) from fallback_exc
                logger.exception("Fallback LLM invocation failed: %s", fallback_exc)
                response_text = ""
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
