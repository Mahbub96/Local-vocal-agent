from __future__ import annotations

import json
import logging
import re
from collections.abc import AsyncIterator
from datetime import datetime, timedelta
from urllib.parse import quote

import httpx

from app.core.settings import get_settings
from app.integrations.ollama.llm import (
    OllamaChatModel,
    build_chat_ollama_for_prefs,
    get_ollama_chat_model,
)
from app.services.effective_assistant_prefs import resolve_effective_assistant_prefs
from app.integrations.tts.tts_locale import prefers_bangla_tts
from app.integrations.search.duckduckgo import DuckDuckGoSearchClient, get_duckduckgo_search_client
from app.integrations.market.price_stats import (
    fetch_market_snapshot_for_query,
    market_snapshot_to_markdown,
)
from app.integrations.time.world_time import (
    extract_iso_clock_from_time_line,
    fetch_local_time_utc_string,
    refine_search_query_for_tool,
    resolve_timezone_for_query,
)
from app.memory.long_term.retriever import LongTermMemoryRetriever
from app.models import Message
from app.services.memory_service import MemoryContext


settings = get_settings()
logger = logging.getLogger(__name__)


class ModelUnavailableError(RuntimeError):
    """Raised when configured Ollama model is missing/unavailable."""


def _llm_chunk_to_text(chunk: object) -> str:
    """Extract incremental text from LangChain / Ollama stream chunks."""
    content = getattr(chunk, "content", chunk)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict) and str(block.get("type")) == "text":
                parts.append(str(block.get("text", "")))
            elif isinstance(block, str):
                parts.append(block)
        return "".join(parts)
    if content is None:
        return ""
    return str(content)


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
    r"(?i)\b("
    r"what(?:'s| is)?\s+(?:the\s+)?time|"
    r"current\s+time|local\s+time|time\s+now|now\s+time|"
    r"what(?:'s| is)?\s+(?:the\s+)?clock|"
    r"timezone(?:\s+now)?|"
    r"সময়\s+কত|এখন\s+কটা\s+বাজে|টাইম\s+কত"
    r")\b"
)
_DATE_QUERY = re.compile(
    r"(?i)\b("
    r"what(?:'s| is)?\s+(?:the\s+)?date|"
    r"today(?:'s|s)?\s+date|current\s+date|date\s+today|"
    r"আজ(?:কের)?\s*তারিখ(?:\s*কত)?|তারিখ\s*কত"
    r")\b"
)
_INTERNET_ACCESS_QUERY = re.compile(
    r"(?i)(\b(internet|online|web|browse|connection|network)\b.*\b(have|can|access|connected|working)\b|"
    r"\bdo you have internet\b|"
    r"\bare you online\b|"
    r"\bcan you browse\b)"
)
_FINANCE_STATS_QUERY = re.compile(
    r"(?i)\b("
    r"stock|share|market|exchange|dse|cse|nasdaq|dow|s&p|"
    r"gold|silver|oil|forex|currency|price|rate|statistics?|stats?|table|chart|"
    r"last\s+\d+\s*(?:day|days|week|weeks|month|months|year|years)|"
    r"today|yesterday|last\s+(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)"
    r")\b"
)
_WEEKDAY_INDEX = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}


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


def _is_finance_or_stats_query(query: str) -> bool:
    return bool(_FINANCE_STATS_QUERY.search(query))


def _prefers_bangla_profile(profile: dict | None) -> bool:
    if not profile:
        return False
    lang = profile.get("language")
    return isinstance(lang, str) and prefers_bangla_tts(lang)


def _localized(profile: dict | None, *, en: str, bn: str) -> str:
    return bn if _prefers_bangla_profile(profile) else en


def _contains_arabic_script(text: str) -> bool:
    return any(
        ("\u0600" <= ch <= "\u06ff")
        or ("\u0750" <= ch <= "\u077f")
        or ("\u08a0" <= ch <= "\u08ff")
        or ("\ufb50" <= ch <= "\ufdff")
        or ("\ufe70" <= ch <= "\ufeff")
        for ch in text
    )


def _is_low_clarity_input(query: str) -> bool:
    t = query.strip()
    if len(t) < 8:
        return False
    if re.search(r"(?i)\b([a-z]{2,})\b(?:\s+\1\b){8,}", t):
        return True
    words = re.findall(r"[A-Za-z\u0980-\u09ff]{2,}", t)
    if len(words) >= 10:
        uniq = {w.lower() for w in words}
        if len(uniq) <= max(2, len(words) // 8):
            return True
        freq: dict[str, int] = {}
        for w in words:
            k = w.lower()
            freq[k] = freq.get(k, 0) + 1
        top = max(freq.values()) if freq else 0
        if top >= 8 and top / max(1, len(words)) >= 0.35:
            return True
    letters = [ch.lower() for ch in t if ch.isalpha()]
    if len(letters) >= 50:
        unique_ratio = len(set(letters)) / max(1, len(letters))
        if unique_ratio < 0.18:
            return True
    return False


def _clarification_for_unclear_input(profile: dict | None) -> str:
    return _localized(
        profile,
        en=(
            "I could not understand that clearly. Please send one short sentence in Bangla or English, "
            "and include your exact question."
        ),
        bn=(
            "আমি ইনপুটটি পরিষ্কারভাবে বুঝতে পারিনি। অনুগ্রহ করে বাংলা বা ইংরেজিতে এক লাইনে ছোট করে "
            "প্রশ্নটি লিখুন।"
        ),
    )


def _rewrite_relative_weekday_in_query(query: str, time_line: str | None) -> str:
    """Resolve 'last sunday' style phrases to concrete ISO date when current date is known."""
    if not time_line:
        return query
    clock = extract_iso_clock_from_time_line(time_line)
    if not clock:
        return query
    try:
        now_dt = datetime.strptime(clock, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return query

    out = query
    for wd, idx in _WEEKDAY_INDEX.items():
        pat = re.compile(rf"(?i)\blast\s+{wd}\b")
        if not pat.search(out):
            continue
        delta = (now_dt.weekday() - idx) % 7
        if delta == 0:
            delta = 7
        target = (now_dt - timedelta(days=delta)).date().isoformat()
        out = pat.sub(f"{wd} ({target})", out)
    return out


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
_NO_INTERNET_CLAIM = re.compile(
    r"(?i)\b(i\s+(?:do not|don't)\s+have\s+(?:real[- ]?time\s+)?internet\s+access|"
    r"simulated\s+environment|cannot\s+browse\s+the\s+internet)\b"
)


def _long_term_context_block(messages: list[Message], *, cap: int | None = None) -> str:
    """Format stored-memory rows for the prompt; trim each row so context fits the model window."""
    if not messages:
        return "No matching memory rows retrieved."
    cap = int(cap if cap is not None else settings.memory_injected_chars_per_message)
    lines: list[str] = []
    for msg in messages:
        body = (msg.content or "").strip()
        if len(body) > cap:
            body = body[:cap] + " …"
        lines.append(f"[{msg.role}] {body}")
    return "\n".join(lines)


def _memory_recall_authority_note() -> str:
    return (
        "Retrieved long-term lines come from this user’s saved chat history (many sessions). "
        "Treat them as ground truth about what was said before when answering recall questions.\n\n"
    )


def _human_voice_guidance() -> str:
    """Steer away from generic LLM tone; keep instructions short so they stay in-context."""
    return (
        "Reply like a real person would—natural, direct, warm when it fits. "
        "Avoid AI-essay habits: no \"I'd be happy to\", \"Certainly!\", \"Great question\", "
        "\"In summary/conclusion\", \"Furthermore\", \"Additionally\", stock openings, or long bullet lists "
        "unless the user clearly wants steps or a list. Prefer short paragraphs; match brevity if they're brief. "
        "If the reply may be read aloud, use a spoken rhythm: short sentences, contractions where natural, "
        "no numbered essay structure unless they asked for a list. "
        "Do not say you're an AI, language model, or chatbot. No em dash section dividers or corporate tone.\n\n"
    )


def _bangla_reply_instruction(profile: dict | None) -> str:
    """Stronger than profile listing alone: tell the LLM to answer in Bangla when preferred."""
    if not profile:
        return ""
    lang = profile.get("language")
    if not isinstance(lang, str) or not prefers_bangla_tts(lang):
        return ""
    return (
        "Preferred response language: Bangla (Bengali). Write the full reply in Bangla using Bengali script, "
        "in a natural spoken style (not formal brochure Bengali unless the topic needs it). "
        "Unless the user clearly asked for another language.\n\n"
    )


def _response_format_instruction(format_pref: str) -> str:
    if format_pref == "table":
        return "Prefer concise markdown tables for statistics when data supports it.\n\n"
    if format_pref == "markdown":
        return "Format responses in clean markdown (headings/lists/tables when useful).\n\n"
    if format_pref == "plain":
        return "Use plain text only; avoid markdown formatting.\n\n"
    return ""


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
    tts = profile.get("tts_playback_speed")
    if isinstance(tts, (int, float)):
        parts.append(f"- Speech playback speed: {float(tts):.2f}× (saved; voice commands can change this)")
    wake = profile.get("assistant_wake_name")
    if isinstance(wake, str) and wake.strip():
        parts.append(f"- Wake name (say this to address the assistant in voice when silent mode is on): {wake.strip()}")
    if profile.get("voice_listen_paused"):
        if profile.get("voice_wake_session_active"):
            parts.append(
                "- Voice silent mode: ON — the user already called you by the wake name; "
                "follow-up voice turns are processed without repeating the wake name until they say stop, "
                "that’s enough, or keep quiet."
            )
        else:
            parts.append(
                "- Voice silent mode: ON — only voice that includes the wake name is processed; text chat still works."
            )
    ov = profile.get("assistant_app_overrides")
    if isinstance(ov, dict) and ov:
        parts.append(
            f"- Custom assistant settings: {len(ov)} override(s) (memory, LLM, search). "
            "Say “show my assistant settings” to list them."
        )
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


def _sanitize_live_data_claims(response: str, *, used_internet: bool) -> str:
    if not used_internet:
        return response
    cleaned = _NO_INTERNET_CLAIM.sub("I have live internet access for this query", response)
    return cleaned.strip()


def should_use_internet_search(
    query: str,
    memory_context: MemoryContext,
    *,
    zone: str | None,
) -> bool:
    """Prefer memory; pull web when there is no semantic hit, or the query clearly needs fresh/online data."""
    prefs = memory_context.effective_prefs or resolve_effective_assistant_prefs(
        memory_context.user_profile
    )
    if prefs.always_web_search:
        return True
    if _is_internet_access_query(query):
        return True
    if _is_finance_or_stats_query(query):
        return True
    if zone is not None:
        return True
    if EXPLICIT_SEARCH.search(query):
        return True
    if REALTIME_PATTERN.search(query):
        return True
    if _is_trivial_utterance(query):
        return False
    if prefs.assistant_search_if_no_memory and not _has_semantic_long_term_hits(memory_context):
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
        self.search_client = search_client or get_duckduckgo_search_client()
        self.llm = (llm or get_ollama_chat_model()).client

    async def run(self, *, query: str, memory_context: MemoryContext) -> dict[str, object]:
        if _is_low_clarity_input(query):
            return {
                "response": _clarification_for_unclear_input(memory_context.user_profile),
                "used_internet": False,
                "used_memory": True,
                "tool_result": json.dumps([], default=str),
            }
        if _prefers_bangla_profile(memory_context.user_profile) and _contains_arabic_script(query):
            return {
                "response": _localized(
                    memory_context.user_profile,
                    en="Please send Bangla in Bengali script or plain English so I can answer correctly.",
                    bn="সঠিক উত্তর দিতে বাংলা হলে বাংলা লিপিতে, নাহলে সরল ইংরেজিতে লিখুন।",
                ),
                "used_internet": False,
                "used_memory": True,
                "tool_result": json.dumps([], default=str),
            }
        zone = resolve_timezone_for_query(query)
        if zone is None and (_is_time_query(query) or _is_date_query(query)):
            zone = _resolve_timezone_from_profile(memory_context.user_profile)
        strict_live = _is_finance_or_stats_query(query)
        if zone is None and strict_live and re.search(r"(?i)\b(dhaka|bangladesh|dse)\b", query):
            zone = "Asia/Dhaka"
        time_line: str | None = None
        weather_snapshot: dict[str, str] | None = None
        if zone:
            time_line = await fetch_local_time_utc_string(zone)
        if _is_weather_query(query):
            weather_snapshot = await _fetch_weather_snapshot(query)

        use_search = should_use_internet_search(query, memory_context, zone=zone)

        prefs = memory_context.effective_prefs or resolve_effective_assistant_prefs(
            memory_context.user_profile
        )
        profile_text = _user_profile_block(memory_context.user_profile)
        long_term_context = _long_term_context_block(
            memory_context.long_term_messages, cap=prefs.memory_injected_chars_per_message
        )
        short_term_context = "\n".join(
            f"[{msg['role']}] {msg['content']}" for msg in memory_context.short_term_messages
        ) or "No recent conversation context."
        web_context = "No internet search was used."
        tool_trace_payload: list[dict[str, object]] = []
        market_markdown: str | None = None

        web_results: list[dict[str, str]] = []
        if use_search:
            normalized_query = _rewrite_relative_weekday_in_query(query, time_line)
            search_q = refine_search_query_for_tool(normalized_query)
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

        if strict_live:
            market_snapshot = await fetch_market_snapshot_for_query(query)
            if market_snapshot:
                market_markdown = market_snapshot_to_markdown(market_snapshot)
                tool_trace_payload.append(
                    {
                        "tool": "market_data_tool",
                        "used": True,
                        "provider": "Yahoo Finance chart API",
                        "symbol": market_snapshot.symbol,
                        "rows": len(market_snapshot.rows),
                    }
                )
            else:
                tool_trace_payload.append(
                    {
                        "tool": "market_data_tool",
                        "used": False,
                        "provider": "Yahoo Finance chart API",
                    }
                )

        if market_markdown:
            tool_trace = json.dumps(tool_trace_payload, default=str)
            return {
                "response": market_markdown,
                "used_internet": True,
                "used_memory": True,
                "tool_result": tool_trace,
            }

        if strict_live and prefs.strict_no_guessing and not web_results:
            tool_trace = json.dumps(tool_trace_payload, default=str)
            return {
                "response": _localized(
                    memory_context.user_profile,
                    en=(
                        "I could not fetch verified live data right now, so I won't generate "
                        "a guessed answer. Please retry in a moment."
                    ),
                    bn=(
                        "এই মুহূর্তে যাচাইকৃত লাইভ ডেটা আনতে পারিনি, তাই অনুমানভিত্তিক উত্তর দিচ্ছি না। "
                        "অনুগ্রহ করে একটু পরে আবার চেষ্টা করুন।"
                    ),
                ),
                "used_internet": True,
                "used_memory": True,
                "tool_result": tool_trace,
            }

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
                "response": _localized(
                    memory_context.user_profile,
                    en=(
                        "I could not fetch live weather data right now from online sources. "
                        "Please retry in a moment."
                    ),
                    bn=(
                        "এই মুহূর্তে অনলাইন উৎস থেকে লাইভ আবহাওয়ার তথ্য আনতে পারিনি। "
                        "অনুগ্রহ করে একটু পরে আবার চেষ্টা করুন।"
                    ),
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
                "response": _localized(
                    memory_context.user_profile,
                    en=(
                        "I could not fetch live time right now from online time providers. "
                        "Please retry in a moment."
                    ),
                    bn=(
                        "এই মুহূর্তে অনলাইন টাইম সার্ভিস থেকে লাইভ সময় আনতে পারিনি। "
                        "অনুগ্রহ করে একটু পরে আবার চেষ্টা করুন।"
                    ),
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
                "response": _localized(
                    memory_context.user_profile,
                    en=(
                        "I could not fetch today's date from live time providers right now. "
                        "Please retry in a moment."
                    ),
                    bn=(
                        "এই মুহূর্তে লাইভ টাইম সার্ভিস থেকে আজকের তারিখ আনতে পারিনি। "
                        "অনুগ্রহ করে একটু পরে আবার চেষ্টা করুন।"
                    ),
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
                "response": _localized(
                    memory_context.user_profile,
                    en=(
                        "I could not confirm internet access right now because live web lookup failed. "
                        "Please check network status and try again."
                    ),
                    bn=(
                        "লাইভ ওয়েব লুকআপ ব্যর্থ হওয়ায় এই মুহূর্তে ইন্টারনেট সংযোগ নিশ্চিত করতে পারিনি। "
                        "নেটওয়ার্ক অবস্থা দেখে আবার চেষ্টা করুন।"
                    ),
                ),
                "used_internet": True,
                "used_memory": True,
                "tool_result": tool_trace,
            }

        prompt = (
            "You are a personal local assistant with long-term memory, short-term context, and optional web search.\n"
            f"{_human_voice_guidance()}"
            f"{_memory_recall_authority_note()}"
            "Answer from long-term and recent conversation when they are enough.\n"
            "Recent conversation is persisted session history from the database; use it for continuity.\n"
            "Never claim you have no real-time internet or browsing access when internet/tool context is present.\n"
            "When a LIVE TIME line is present, copy the exact YYYY-MM-DD HH:MM:SS from it into your answer.\n"
            "FORBIDDEN: the phrase 'insert' near 'time' and 'here', bracket templates, TBD, or [placeholder] for time.\n"
            "When web snippets or LIVE TIME are provided, use them for facts; do not invent times.\n"
            "If the user asks for finance/statistics/table/range data and web snippets are missing, "
            "DO NOT fabricate numbers or example tables—state that live data is unavailable.\n\n"
            f"{_response_format_instruction(prefs.response_format_preference)}"
            f"{_bangla_reply_instruction(memory_context.user_profile)}"
            f"{profile_text}"
            f"Recent conversation:\n{short_term_context}\n\n"
            f"Retrieved long-term memory (vector + keyword search over stored history):\n{long_term_context}\n\n"
            f"Internet / live data (may be empty):\n{web_context}\n\n"
            f"User query:\n{query}"
        )
        llm = build_chat_ollama_for_prefs(prefs)
        try:
            result = await llm.ainvoke(prompt)
            response_text = str(getattr(result, "content", result)).strip()
            if not response_text:
                raise ValueError("Model produced an empty output.")
            response_text = _strip_llm_time_placeholders(response_text, time_line)
            response_text = _sanitize_live_data_claims(response_text, used_internet=use_search)
            tool_trace = json.dumps(tool_trace_payload, default=str)
        except Exception as exc:
            if _is_model_not_found_error(exc):
                raise ModelUnavailableError(
                    f"Ollama model '{settings.ollama_model}' is not available locally. "
                    f"Pull it first (e.g. `ollama pull {settings.ollama_model}`) or set OLLAMA_MODEL."
                ) from exc
            logger.exception("LLM execution failed; applying minimal fallback prompt: %s", exc)
            try:
                fallback_result = await llm.ainvoke(query)
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
                response_text = _sanitize_live_data_claims(response_text, used_internet=use_search)
            tool_trace = json.dumps([], default=str)
        return {
            "response": response_text,
            "used_internet": use_search,
            "used_memory": True,
            "tool_result": tool_trace,
        }

    async def stream_run(
        self,
        *,
        query: str,
        memory_context: MemoryContext,
    ) -> AsyncIterator[str | dict[str, object]]:
        """Yield text deltas, then a final dict (same shape as `run`)."""
        if _is_low_clarity_input(query):
            res = {
                "response": _clarification_for_unclear_input(memory_context.user_profile),
                "used_internet": False,
                "used_memory": True,
                "tool_result": json.dumps([], default=str),
            }
            yield res["response"]
            yield res
            return
        if _prefers_bangla_profile(memory_context.user_profile) and _contains_arabic_script(query):
            res = {
                "response": _localized(
                    memory_context.user_profile,
                    en="Please send Bangla in Bengali script or plain English so I can answer correctly.",
                    bn="সঠিক উত্তর দিতে বাংলা হলে বাংলা লিপিতে, নাহলে সরল ইংরেজিতে লিখুন।",
                ),
                "used_internet": False,
                "used_memory": True,
                "tool_result": json.dumps([], default=str),
            }
            yield res["response"]
            yield res
            return
        zone = resolve_timezone_for_query(query)
        if zone is None and (_is_time_query(query) or _is_date_query(query)):
            zone = _resolve_timezone_from_profile(memory_context.user_profile)
        strict_live = _is_finance_or_stats_query(query)
        if zone is None and strict_live and re.search(r"(?i)\b(dhaka|bangladesh|dse)\b", query):
            zone = "Asia/Dhaka"
        time_line: str | None = None
        weather_snapshot: dict[str, str] | None = None
        if zone:
            time_line = await fetch_local_time_utc_string(zone)
        if _is_weather_query(query):
            weather_snapshot = await _fetch_weather_snapshot(query)

        use_search = should_use_internet_search(query, memory_context, zone=zone)

        prefs = memory_context.effective_prefs or resolve_effective_assistant_prefs(
            memory_context.user_profile
        )
        profile_text = _user_profile_block(memory_context.user_profile)
        long_term_context = _long_term_context_block(
            memory_context.long_term_messages, cap=prefs.memory_injected_chars_per_message
        )
        short_term_context = "\n".join(
            f"[{msg['role']}] {msg['content']}" for msg in memory_context.short_term_messages
        ) or "No recent conversation context."
        web_context = "No internet search was used."
        tool_trace_payload: list[dict[str, object]] = []
        market_markdown: str | None = None

        web_results: list[dict[str, str]] = []
        if use_search:
            normalized_query = _rewrite_relative_weekday_in_query(query, time_line)
            search_q = refine_search_query_for_tool(normalized_query)
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

        if strict_live:
            market_snapshot = await fetch_market_snapshot_for_query(query)
            if market_snapshot:
                market_markdown = market_snapshot_to_markdown(market_snapshot)
                tool_trace_payload.append(
                    {
                        "tool": "market_data_tool",
                        "used": True,
                        "provider": "Yahoo Finance chart API",
                        "symbol": market_snapshot.symbol,
                        "rows": len(market_snapshot.rows),
                    }
                )
            else:
                tool_trace_payload.append(
                    {
                        "tool": "market_data_tool",
                        "used": False,
                        "provider": "Yahoo Finance chart API",
                    }
                )

        if market_markdown:
            tool_trace = json.dumps(tool_trace_payload, default=str)
            res = {
                "response": market_markdown,
                "used_internet": True,
                "used_memory": True,
                "tool_result": tool_trace,
            }
            yield res["response"]
            yield res
            return

        if strict_live and prefs.strict_no_guessing and not web_results:
            tool_trace = json.dumps(tool_trace_payload, default=str)
            res = {
                "response": _localized(
                    memory_context.user_profile,
                    en=(
                        "I could not fetch verified live data right now, so I won't generate "
                        "a guessed answer. Please retry in a moment."
                    ),
                    bn=(
                        "এই মুহূর্তে যাচাইকৃত লাইভ ডেটা আনতে পারিনি, তাই অনুমানভিত্তিক উত্তর দিচ্ছি না। "
                        "অনুগ্রহ করে একটু পরে আবার চেষ্টা করুন।"
                    ),
                ),
                "used_internet": True,
                "used_memory": True,
                "tool_result": tool_trace,
            }
            yield res["response"]
            yield res
            return

        if weather_snapshot and _is_weather_query(query):
            tool_trace = json.dumps(tool_trace_payload, default=str)
            res = {
                "response": weather_snapshot["summary"],
                "used_internet": True,
                "used_memory": True,
                "tool_result": tool_trace,
            }
            yield res["response"]
            yield res
            return
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
                res = {
                    "response": line,
                    "used_internet": True,
                    "used_memory": True,
                    "tool_result": tool_trace,
                }
                yield res["response"]
                yield res
                return
            tool_trace = json.dumps(tool_trace_payload, default=str)
            res = {
                "response": _localized(
                    memory_context.user_profile,
                    en=(
                        "I could not fetch live weather data right now from online sources. "
                        "Please retry in a moment."
                    ),
                    bn=(
                        "এই মুহূর্তে অনলাইন উৎস থেকে লাইভ আবহাওয়ার তথ্য আনতে পারিনি। "
                        "অনুগ্রহ করে একটু পরে আবার চেষ্টা করুন।"
                    ),
                ),
                "used_internet": True,
                "used_memory": True,
                "tool_result": tool_trace,
            }
            yield res["response"]
            yield res
            return

        if _is_time_query(query):
            tool_trace = json.dumps(tool_trace_payload, default=str)
            compact = _compact_time_response(time_line)
            if compact:
                res = {
                    "response": compact,
                    "used_internet": True,
                    "used_memory": True,
                    "tool_result": tool_trace,
                }
                yield res["response"]
                yield res
                return
            res = {
                "response": _localized(
                    memory_context.user_profile,
                    en=(
                        "I could not fetch live time right now from online time providers. "
                        "Please retry in a moment."
                    ),
                    bn=(
                        "এই মুহূর্তে অনলাইন টাইম সার্ভিস থেকে লাইভ সময় আনতে পারিনি। "
                        "অনুগ্রহ করে একটু পরে আবার চেষ্টা করুন।"
                    ),
                ),
                "used_internet": True,
                "used_memory": True,
                "tool_result": tool_trace,
            }
            yield res["response"]
            yield res
            return

        if _is_date_query(query):
            tool_trace = json.dumps(tool_trace_payload, default=str)
            compact_date = _compact_date_response(time_line)
            if compact_date:
                res = {
                    "response": compact_date,
                    "used_internet": True,
                    "used_memory": True,
                    "tool_result": tool_trace,
                }
                yield res["response"]
                yield res
                return
            res = {
                "response": _localized(
                    memory_context.user_profile,
                    en=(
                        "I could not fetch today's date from live time providers right now. "
                        "Please retry in a moment."
                    ),
                    bn=(
                        "এই মুহূর্তে লাইভ টাইম সার্ভিস থেকে আজকের তারিখ আনতে পারিনি। "
                        "অনুগ্রহ করে একটু পরে আবার চেষ্টা করুন।"
                    ),
                ),
                "used_internet": True,
                "used_memory": True,
                "tool_result": tool_trace,
            }
            yield res["response"]
            yield res
            return

        if _is_internet_access_query(query):
            tool_trace = json.dumps(tool_trace_payload, default=str)
            if web_results:
                res = {
                    "response": (
                        "Yes — internet access is currently available. "
                        f"I can fetch live web results (received {len(web_results)} result snippets just now)."
                    ),
                    "used_internet": True,
                    "used_memory": True,
                    "tool_result": tool_trace,
                }
                yield res["response"]
                yield res
                return
            res = {
                "response": _localized(
                    memory_context.user_profile,
                    en=(
                        "I could not confirm internet access right now because live web lookup failed. "
                        "Please check network status and try again."
                    ),
                    bn=(
                        "লাইভ ওয়েব লুকআপ ব্যর্থ হওয়ায় এই মুহূর্তে ইন্টারনেট সংযোগ নিশ্চিত করতে পারিনি। "
                        "নেটওয়ার্ক অবস্থা দেখে আবার চেষ্টা করুন।"
                    ),
                ),
                "used_internet": True,
                "used_memory": True,
                "tool_result": tool_trace,
            }
            yield res["response"]
            yield res
            return

        prompt = (
            "You are a personal local assistant with long-term memory, short-term context, and optional web search.\n"
            f"{_human_voice_guidance()}"
            f"{_memory_recall_authority_note()}"
            "Answer from long-term and recent conversation when they are enough.\n"
            "Recent conversation is persisted session history from the database; use it for continuity.\n"
            "Never claim you have no real-time internet or browsing access when internet/tool context is present.\n"
            "When a LIVE TIME line is present, copy the exact YYYY-MM-DD HH:MM:SS from it into your answer.\n"
            "FORBIDDEN: the phrase 'insert' near 'time' and 'here', bracket templates, TBD, or [placeholder] for time.\n"
            "When web snippets or LIVE TIME are provided, use them for facts; do not invent times.\n"
            "If the user asks for finance/statistics/table/range data and web snippets are missing, "
            "DO NOT fabricate numbers or example tables—state that live data is unavailable.\n\n"
            f"{_response_format_instruction(prefs.response_format_preference)}"
            f"{_bangla_reply_instruction(memory_context.user_profile)}"
            f"{profile_text}"
            f"Recent conversation:\n{short_term_context}\n\n"
            f"Retrieved long-term memory (vector + keyword search over stored history):\n{long_term_context}\n\n"
            f"Internet / live data (may be empty):\n{web_context}\n\n"
            f"User query:\n{query}"
        )
        acc_list: list[str] = []
        tool_trace = json.dumps(tool_trace_payload, default=str)
        llm = build_chat_ollama_for_prefs(prefs)
        # Smaller SSE token payloads so the UI can render progressively (LangChain may emit large chunks).
        _SSE_CHAR_STEP = 4
        try:
            async for chunk in llm.astream(prompt):
                d = _llm_chunk_to_text(chunk)
                if d:
                    acc_list.append(d)
                    for i in range(0, len(d), _SSE_CHAR_STEP):
                        yield d[i : i + _SSE_CHAR_STEP]
            response_text = "".join(acc_list).strip()
            if not response_text:
                raise ValueError("Model produced an empty output.")
            response_text = _strip_llm_time_placeholders(response_text, time_line)
            response_text = _sanitize_live_data_claims(response_text, used_internet=use_search)
            tool_trace = json.dumps(tool_trace_payload, default=str)
        except Exception as exc:
            if _is_model_not_found_error(exc):
                raise ModelUnavailableError(
                    f"Ollama model '{settings.ollama_model}' is not available locally. "
                    f"Pull it first (e.g. `ollama pull {settings.ollama_model}`) or set OLLAMA_MODEL."
                ) from exc
            logger.exception("LLM execution failed; applying minimal fallback prompt: %s", exc)
            acc_fb: list[str] = []
            try:
                async for chunk in llm.astream(query):
                    d = _llm_chunk_to_text(chunk)
                    if d:
                        acc_fb.append(d)
                        for i in range(0, len(d), _SSE_CHAR_STEP):
                            yield d[i : i + _SSE_CHAR_STEP]
                response_text = "".join(acc_fb).strip()
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
                yield response_text
            else:
                response_text = _strip_llm_time_placeholders(response_text, time_line)
                response_text = _sanitize_live_data_claims(response_text, used_internet=use_search)
            tool_trace = json.dumps([], default=str)
        yield {
            "response": response_text,
            "used_internet": use_search,
            "used_memory": True,
            "tool_result": tool_trace,
        }
