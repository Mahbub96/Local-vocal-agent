"""Detect voice/chat commands that adjust per-user speech (TTS) preferences."""

from __future__ import annotations

import re
from typing import Any

from app.core.settings import get_settings


# Order: first matching rule wins (most specific patterns first).
_RESET = re.compile(
    r"(?i)\b(?:reset|restore)\s+(?:speech|tts|voice|reading)?\s*(?:speed|tempo|rate)|\b(?:speech|voice|tts)\s+speed\s+(?:to\s+)?default|"
    r"\bback\s+to\s+(?:default|normal)\s+(?:speech\s+)?speed|\bnormal\s+(?:speech\s+)?speed\b"
)

_ABSOLUTE = re.compile(
    r"(?i)\b(?:speech|tts|voice|playback|reading)\s+speed\s*(?:=|:|to|at)\s*([0-9]+(?:\.[0-9]+)?)\b|"
    r"\bspeak(?:ing)?\s+at\s+([0-9]+(?:\.[0-9]+)?)\s*(?:x\s*)?(?:speed|times)?\b|"
    r"\brate\s*(?:=|:|to)\s*([0-9]+(?:\.[0-9]+)?)\b"
)

_MUCH_FASTER = re.compile(
    r"(?i)\b(?:much|way|a lot|lots)\s+faster\b|\bfaster\s+please\b|\bmax(?:imum)?\s+speed\b"
)
_SLIGHTLY_FASTER = re.compile(
    r"(?i)\b(?:slightly|a little|a bit|little bit|somewhat)\s+faster\b|"
    r"\b(?:speak|talk)\s+(?:slightly|a\s+bit|a\s+little)\s+faster\b|\ba\s+bit\s+faster\b"
)
_FASTER = re.compile(
    r"(?i)\b(?:speed|pick)\s+up\b|\bspeed\s+up\b|\b(?:speak|talk)\s+faster\b|\bfaster\s+(?:please|speech|voice)?\b"
)

_MUCH_SLOWER = re.compile(
    r"(?i)\b(?:much|way|a lot)\s+slower\b|\bslow(?:er)?\s+down\s+a lot\b"
)
_SLIGHTLY_SLOWER = re.compile(
    r"(?i)\b(?:slightly|a little|a bit|little bit|somewhat)\s+slower\b|"
    r"\b(?:speak|talk)\s+(?:slightly|a\s+bit|a\s+little)\s+slower\b|\ba\s+bit\s+slower\b"
)
_SLOWER = re.compile(
    r"(?i)\b(?:speak|talk)\s+slower\b|\bslow(?:er)?\s+down\b|\bslower\s+please\b"
)


def _clamp(speed: float) -> float:
    return max(0.85, min(2.0, float(speed)))


def _base_speed(profile: dict[str, Any] | None) -> float:
    settings = get_settings()
    if profile:
        raw = profile.get("tts_playback_speed")
        if isinstance(raw, (int, float)):
            return float(raw)
    return float(settings.tts_playback_speed)


def merge_speech_preferences_from_message(
    profile: dict[str, Any],
    message: str,
) -> tuple[dict[str, Any], bool]:
    """
    Apply phrases like 'speak slightly faster' to ``tts_playback_speed`` in a profile copy.

    Returns (updated_profile, changed).
    """
    text = message.strip()
    if not text:
        return profile, False

    merged = dict(profile)
    base = _base_speed(merged)

    if _RESET.search(text):
        if "tts_playback_speed" in merged:
            del merged["tts_playback_speed"]
            return merged, True
        return merged, False

    m = _ABSOLUTE.search(text)
    if m:
        for g in m.groups():
            if g is None:
                continue
            try:
                val = float(g)
            except ValueError:
                continue
            val = _clamp(val)
            if merged.get("tts_playback_speed") == val:
                return merged, False
            merged["tts_playback_speed"] = val
            return merged, True

    delta = 0.0
    if _MUCH_FASTER.search(text):
        delta = 0.22
    elif _SLIGHTLY_FASTER.search(text):
        delta = 0.09
    elif _FASTER.search(text):
        delta = 0.14
    elif _MUCH_SLOWER.search(text):
        delta = -0.22
    elif _SLIGHTLY_SLOWER.search(text):
        delta = -0.09
    elif _SLOWER.search(text):
        delta = -0.14

    if delta == 0.0:
        return merged, False

    new_speed = _clamp(base + delta)
    if abs(new_speed - base) < 1e-6:
        return merged, False
    merged["tts_playback_speed"] = new_speed
    return merged, True
