"""Map stored profile language labels to TTS/STT locale choices."""

from __future__ import annotations


def prefers_bangla_tts(language: str | None) -> bool:
    """True when profile language indicates Bangla (matches UI e.g. বাংলা (Bangla))."""
    if not language:
        return False
    raw = str(language).strip()
    if not raw:
        return False
    low = raw.lower()
    if "bangla" in low or "bengali" in low:
        return True
    if "বাংলা" in raw:
        return True
    return low in {"bn", "bn-bd"}
