"""Normalize assistant text before TTS to avoid crashes, junk audio, and runaway length."""

from __future__ import annotations

import re

# Strip C0 controls except tab/newline; normalize newlines to space.
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
# Collapse repeated punctuation that can confuse some models (optional light touch).
_MULTI_SPACE = re.compile(r"\s+")


def prepare_tts_text(raw: str, max_chars: int) -> str:
    """
    Return safe, bounded plain text for Coqui. Empty string means caller should skip TTS.
    """
    if not raw:
        return ""
    t = _CONTROL_CHARS.sub(" ", raw)
    t = t.replace("\n", " ").replace("\t", " ")
    t = _MULTI_SPACE.sub(" ", t).strip()
    if not t:
        return ""
    if len(t) > max_chars:
        t = t[: max(0, max_chars - 1)].rstrip() + "…"
    return t
