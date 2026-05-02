"""Lightweight intent signals and web-search policy (regex + heuristics)."""

from __future__ import annotations

import re
from typing import Any, Protocol

# Structural type only — avoids importing memory_service / pydantic at module load (tests, lightweight imports).


class _MemoryForSearch(Protocol):
    user_profile: Any
    effective_prefs: Any | None
    long_term_messages: Any

EXPLICIT_SEARCH = re.compile(r"\bsearch\b", re.IGNORECASE)
# No bare "time" — avoids "take your time", "on time", etc. Use is_time_query() for clock asks.
REALTIME_PATTERN = re.compile(
    r"\b(weather|news|latest|today|current|now|stock|price|forecast|"
    r"headline|recent|timezone|clock|lookup|online|live)\b",
    re.IGNORECASE,
)

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
# User asks if the assistant can "hear" them / mic / voice path (EN + BN).
_AUDIO_CHANNEL_CHECK = re.compile(
    r"(?i)(?:"
    r"\bcan you hear me\b|\bdo you hear me\b|\bare you hearing (?:me)?\b|"
    r"\bhear me\??|\bis (?:the )?(?:mic|microphone)\b|\bmic (?:ok|check|working)\b|"
    r"শুনতে\s*পাচ্ছ[ো]?|শুনছ(?:ো|ি)?|কণ্ঠ|মাইক|মাইক্রোফোন|অডিও"
    r")"
)

_FINANCE_STATS_QUERY = re.compile(
    r"(?i)\b("
    r"stock|share|market|exchange|dse|cse|nasdaq|dow|s&p|"
    r"gold|silver|oil|forex|currency|price|rate|statistics?|stats?|table|chart|"
    r"last\s+\d+\s*(?:day|days|week|weeks|month|months|year|years)|"
    r"today|yesterday|last\s+(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)"
    r")\b"
)
# Whole-line reassurance only — used to skip assistant_search_if_no_memory (not global search rules).
_REASSURANCE_CHITCHAT_FULL = re.compile(
    r"(?i)^\s*(?:please\s+)?(?:(?:take|have)\s+your\s+time|no\s+rush|don'?t\s+rush|"
    r"whenever\s+you(?:'re|\s+are)\s+ready|that'?s\s+ok(?:ay)?|it'?s\s+fine|all\s+good)"
    r"(?:\s*[.!…]*)?\s*$"
)

WEEKDAY_INDEX = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}


def is_trivial_utterance(query: str) -> bool:
    t = query.strip()
    if len(t) < 2:
        return True
    if len(t) <= 64 and _TRIVIAL_UTTERANCE.match(t):
        return True
    return False


def is_weather_query(query: str) -> bool:
    return bool(_WEATHER_QUERY.search(query))


def is_time_query(query: str) -> bool:
    return bool(_TIME_QUERY.search(query))


def is_date_query(query: str) -> bool:
    return bool(_DATE_QUERY.search(query))


def is_internet_access_query(query: str) -> bool:
    return bool(_INTERNET_ACCESS_QUERY.search(query))


def is_finance_or_stats_query(query: str) -> bool:
    return bool(_FINANCE_STATS_QUERY.search(query))


def is_audio_channel_check_query(query: str) -> bool:
    """True when the user checks hearing/mic/voice (common in voice UI)."""
    return bool(_AUDIO_CHANNEL_CHECK.search(query))


def has_semantic_long_term_hits(memory_context: _MemoryForSearch) -> bool:
    return len(memory_context.long_term_messages) > 0


def should_use_internet_search(
    query: str,
    memory_context: _MemoryForSearch,
    *,
    zone: str | None,
) -> bool:
    prefs = memory_context.effective_prefs
    if prefs is None:
        from app.services.effective_assistant_prefs import resolve_effective_assistant_prefs

        prefs = resolve_effective_assistant_prefs(memory_context.user_profile)
    if prefs.always_web_search:
        return True
    if is_internet_access_query(query):
        return True
    if is_finance_or_stats_query(query):
        return True
    if zone is not None:
        return True
    if EXPLICIT_SEARCH.search(query):
        return True
    if is_time_query(query) or is_date_query(query) or is_weather_query(query):
        return True
    if REALTIME_PATTERN.search(query):
        return True
    if is_trivial_utterance(query):
        return False
    if prefs.assistant_search_if_no_memory and not has_semantic_long_term_hits(memory_context):
        if is_audio_channel_check_query(query) or _REASSURANCE_CHITCHAT_FULL.match(query.strip()):
            return False
        return True
    return False


def classify_intent_label(query: str) -> str:
    if is_weather_query(query):
        return "weather"
    if is_time_query(query):
        return "time"
    if is_date_query(query):
        return "date"
    if is_finance_or_stats_query(query):
        return "finance_stats"
    if is_internet_access_query(query):
        return "internet_meta"
    if EXPLICIT_SEARCH.search(query) or REALTIME_PATTERN.search(query):
        return "search_or_live"
    return "general"
