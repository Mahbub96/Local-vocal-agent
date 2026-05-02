"""Task-based policy: when input/output script rules may relax for voice-like conversational tasks.

Strict tasks (finance, medical, live structured facts, etc.) keep full validation.
"""

from __future__ import annotations

import re
from enum import Enum


class TaskType(str, Enum):
    """High-level task bucket for voice vs strict handling."""

    CASUAL_CHAT = "casual_chat"
    GENERAL_QNA = "general_qna"
    ASSISTANT_CONVERSATION = "assistant_conversation"
    SMALL_TALK = "small_talk"
    VOICE_COMMANDS = "voice_commands"
    FINANCE_MARKET = "finance_market"
    MEDICAL_LEGAL_CRITICAL = "medical_legal_critical"
    SYSTEM_COMMAND = "system_command"
    STRUCTURED_DATA = "structured_data"
    SEARCH_PRECISION = "search_precision"


_VOICE_RELAXED_FROZEN = frozenset(
    {
        TaskType.CASUAL_CHAT,
        TaskType.GENERAL_QNA,
        TaskType.ASSISTANT_CONVERSATION,
        TaskType.SMALL_TALK,
        TaskType.VOICE_COMMANDS,
    }
)

_MEDICAL_LEGAL = re.compile(
    r"(?i)\b(legal|medical|lawyer|attorney|lawsuit|diagnosis|prescription|treatment|sue|litigation)\b|"
    r"(আইন|চিকিৎসা|ডাক্তার|ওষুধ|মামলা|ঝুঁকি)",
)

_SYSTEMISH = re.compile(
    r"(?i)\b(show|set|open|delete|clear|export|import|configure)\s+(my\s+)?(assistant|settings|profile|memory)\b|"
    r"\bassistant_app_overrides\b|voice_listen|wake\s*name",
)

_VOICE_UI = re.compile(
    r"(?i)\b(stop\s+(speaking|playback)|resume\s+listening|silent\s+mode)\b|^(থামো|চুপ|বন্ধ করো)\b",
)


def classify_task_type(query: str, *, voice_turn: bool = False) -> TaskType:
    """
    Rule-based task label. Order matters: stricter detectors first.

    For voice-only: short utterances that would default to ``general_qna`` map to ``casual_chat``
    so routing stays listener-like (per product fallback).
    """
    from app.agents.intent_signals import (
        EXPLICIT_SEARCH,
        is_date_query,
        is_finance_or_stats_query,
        is_time_query,
        is_trivial_utterance,
        is_weather_query,
    )

    q = (query or "").strip()
    if not q:
        return TaskType.GENERAL_QNA

    if _MEDICAL_LEGAL.search(q):
        return TaskType.MEDICAL_LEGAL_CRITICAL
    if is_finance_or_stats_query(q):
        return TaskType.FINANCE_MARKET
    if is_weather_query(q) or is_time_query(q) or is_date_query(q):
        return TaskType.STRUCTURED_DATA
    if EXPLICIT_SEARCH.search(q):
        return TaskType.SEARCH_PRECISION
    if _SYSTEMISH.search(q):
        return TaskType.SYSTEM_COMMAND
    if _VOICE_UI.search(q):
        return TaskType.VOICE_COMMANDS
    if is_trivial_utterance(q):
        return TaskType.SMALL_TALK
    if re.search(
        r"(?i)\b(what\s+can\s+you|who\s+are\s+you|help\s+me\s+with|your\s+capabilities|what\s+do\s+you\s+do)\b",
        q,
    ):
        return TaskType.ASSISTANT_CONVERSATION
    words = q.split()
    if len(q) < 48 and len(words) <= 8 and "\n" not in q:
        return TaskType.CASUAL_CHAT
    if voice_turn and len(q) < 100 and len(words) <= 10:
        return TaskType.CASUAL_CHAT
    return TaskType.GENERAL_QNA


def apply_voice_mode(task_type: TaskType) -> bool:
    """True only for conversational / voice-friendly task buckets (relaxed script path)."""
    return task_type in _VOICE_RELAXED_FROZEN


def normalize_voice_input_lightly(text: str) -> str:
    """Strip zero-width junk and collapse whitespace; no semantic rewrite."""
    t = (text or "").replace("\u200b", "").replace("\u200c", "").replace("\ufeff", "")
    return re.sub(r"\s+", " ", t).strip()


def is_voice_input(text: str) -> bool:
    """
    Heuristic for noisy ASR / run-on transcripts.

    Only meaningful when combined with ``apply_voice_mode(task_type)`` (see assistant).
    """
    t = (text or "").strip()
    if len(t) < 6:
        return False
    punct = sum(1 for c in t if c in ".!?।…")
    if len(t) > 100 and punct <= 1:
        return True
    if re.search(r"\b(\w{2,})(\s+\1){2,}", t, re.IGNORECASE):
        return True
    return False
