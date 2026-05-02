"""Input language detection and response language targeting.

Uses the Bengali Unicode block (U+0980–U+09FF) vs Latin letters to classify input.
``resolve_response_target`` combines profile (e.g. user prefers Bangla) with detection.
"""

from __future__ import annotations

from enum import Enum

from app.integrations.tts.tts_locale import prefers_bangla_tts


class InputLanguageKind(str, Enum):
    """Rough classification of the user's message (script + mix)."""

    EMPTY = "empty"
    BENGALI_DOMINANT = "bengali_dominant"
    ENGLISH_DOMINANT = "english_dominant"
    MIXED = "mixed"


class ResponseLanguageTarget(str, Enum):
    """How the assistant should shape the reply in prompts and script policy."""

    BENGALI_SCRIPT = "bengali_script"
    ENGLISH = "english"
    BANGLISH = "banglish"


def detect_input_language(text: str) -> InputLanguageKind:
    """
    Classify user text using Bengali Unicode block vs Latin letters.

    Mixed indicates plausible Banglish / code-switch (both scripts meaningfully present).
    """
    t = (text or "").strip()
    if not t:
        return InputLanguageKind.EMPTY

    bengali_letters = sum(1 for ch in t if "\u0980" <= ch <= "\u09ff")
    latin_letters = sum(1 for ch in t if "a" <= ch.lower() <= "z")
    letters = bengali_letters + latin_letters
    if letters == 0:
        return InputLanguageKind.MIXED

    r_bn = bengali_letters / letters
    r_lat = latin_letters / letters

    if bengali_letters >= 2 and latin_letters >= 2 and r_bn >= 0.2 and r_lat >= 0.2:
        return InputLanguageKind.MIXED
    if bengali_letters >= 1 and latin_letters >= 1 and min(r_bn, r_lat) >= 0.12:
        return InputLanguageKind.MIXED
    if r_bn >= 0.38:
        return InputLanguageKind.BENGALI_DOMINANT
    if latin_letters > 0 and bengali_letters == 0:
        return InputLanguageKind.ENGLISH_DOMINANT
    if r_lat >= 0.62:
        return InputLanguageKind.ENGLISH_DOMINANT
    if bengali_letters > 0:
        return InputLanguageKind.BENGALI_DOMINANT
    return InputLanguageKind.ENGLISH_DOMINANT


def prefers_bangla_profile(profile: dict | None) -> bool:
    if not profile:
        return False
    lang = profile.get("language")
    return isinstance(lang, str) and prefers_bangla_tts(lang)


def resolve_response_target(
    profile: dict | None,
    detected: InputLanguageKind,
) -> ResponseLanguageTarget:
    """
    Profile preference for Bangla forces full Bengali-script replies.

    Otherwise mirror detected input: Bangla-dominant → Bengali script only;
    English-dominant → English; mixed → Banglish.
    """
    if prefers_bangla_profile(profile):
        return ResponseLanguageTarget.BENGALI_SCRIPT
    if detected == InputLanguageKind.EMPTY:
        return ResponseLanguageTarget.ENGLISH
    if detected == InputLanguageKind.BENGALI_DOMINANT:
        return ResponseLanguageTarget.BENGALI_SCRIPT
    if detected == InputLanguageKind.ENGLISH_DOMINANT:
        return ResponseLanguageTarget.ENGLISH
    return ResponseLanguageTarget.BANGLISH


def input_language_note(detected: InputLanguageKind) -> str:
    """One-line hint for the model (internal context, not shown to the user)."""
    if detected == InputLanguageKind.BENGALI_DOMINANT:
        return "User message is primarily in Bangla (Bengali script).\n"
    if detected == InputLanguageKind.ENGLISH_DOMINANT:
        return "User message is primarily in English.\n"
    if detected == InputLanguageKind.MIXED:
        return (
            "User message mixes Bangla and English; reply in natural Banglish—Bangla flow with English "
            "where bilingual speakers would, not word-by-word alternation.\n"
        )
    return ""
