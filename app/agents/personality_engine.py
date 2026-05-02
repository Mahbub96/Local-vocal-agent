"""Personality and response-shape hints for prompts (no LLM calls; prompt text only).

Maps stored profile fields to tone instructions and scales reply depth to query length.
"""

from __future__ import annotations

from enum import Enum


class ToneMode(str, Enum):
    """High-level voice the assistant should adopt."""

    FRIENDLY = "friendly"
    CASUAL = "casual"
    PROFESSIONAL = "professional"


def _resolve_tone_mode(profile: dict | None) -> ToneMode:
    if not profile:
        return ToneMode.FRIENDLY
    raw = profile.get("assistant_tone") or profile.get("tone")
    if not isinstance(raw, str):
        return ToneMode.FRIENDLY
    low = raw.strip().lower()
    if low in ("friendly", "warm", "relaxed"):
        return ToneMode.FRIENDLY
    if low in ("casual", "informal", "chill"):
        return ToneMode.CASUAL
    if low in ("professional", "formal", "neutral", "matter-of-fact", "work"):
        return ToneMode.PROFESSIONAL
    return ToneMode.FRIENDLY


def personality_voice_block(profile: dict | None) -> str:
    """
    How the assistant should *feel*—subtle human traits via instructions, not post-hoc rewriting.

    Keeps traits light: avoid prescribing fake typos; focus on warmth and natural flow.
    """
    mode = _resolve_tone_mode(profile)
    if mode == ToneMode.FRIENDLY:
        return (
            "Personality: sound like a helpful friend in Bangladesh—warm, direct, not performative. "
            "It is fine to sound slightly informal; do not be stiff or customer-service scripted.\n\n"
        )
    if mode == ToneMode.CASUAL:
        return (
            "Personality: relaxed and everyday—short clauses, like chatting on WhatsApp, but still clear and respectful. "
            "No slang for shock value; stay understandable.\n\n"
        )
    return (
        "Personality: clear and professional but still human—no corporate brochure, no stiff legalese. "
        "Warmth is OK in one short phrase if natural; avoid chumminess.\n\n"
    )


def _query_stats(query: str) -> tuple[int, int]:
    t = (query or "").strip()
    return len(t), len(t.split())


def response_length_style_block(query: str) -> str:
    """
    Match response shape to query complexity: short questions → concise answers.

    The model still decides wording; this only sets expectations in the prompt.
    """
    n_chars, n_words = _query_stats(query)
    if n_chars < 50 and n_words < 12:
        return (
            "Response length: the user message is short—answer in a few tight sentences unless they clearly "
            "asked for detail, steps, or a list. No preamble.\n\n"
        )
    if n_chars < 220 and n_words < 45:
        return (
            "Response length: keep it compact—one or two short paragraphs unless the topic needs more. "
            "Start with the answer, then add only useful context.\n\n"
        )
    return (
        "Response length: the question is detailed—you may use a clear structure (short sections or bullets) "
        "only if it helps readability; still avoid essay tone and filler paragraphs.\n\n"
    )
