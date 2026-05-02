"""Normalize assistant text before TTS to avoid crashes, junk audio, and runaway length."""

from __future__ import annotations

import re

# Strip C0 controls except tab/newline; normalize newlines to space.
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
# Collapse repeated punctuation that can confuse some models (optional light touch).
_MULTI_SPACE = re.compile(r"\s+")
# Emoji / pictographs: if left as their own Coqui "sentence", vocab strips them → empty input
# and Tacotron2 crashes (conv kernel > sequence length). Remove before synthesis.
_EMOJI_AND_SYMBOLS = re.compile(
    "["
    "\U0001F1E6-\U0001F1FF"
    "\U0001F300-\U0001F5FF"
    "\U0001F600-\U0001F64F"
    "\U0001F680-\U0001F6FF"
    "\U0001F700-\U0001F77F"
    "\U0001F780-\U0001F7FF"
    "\U0001F800-\U0001F8FF"
    "\U0001F900-\U0001F9FF"
    "\U0001FA00-\U0001FA6F"
    "\U0001FA70-\U0001FAFF"
    "\U00002600-\U000026FF"
    "\U00002700-\U000027BF"
    "\U0000FE00-\U0000FE0F"
    "\U0000200D"
    "]+",
    flags=re.UNICODE,
)
_FENCED_CODE_BLOCK = re.compile(r"```[\s\S]*?```", flags=re.MULTILINE)
_INLINE_CODE = re.compile(r"`([^`]+)`")
_MARKDOWN_LINK = re.compile(r"\[([^\]]+)\]\([^)]+\)")
_URL = re.compile(r"https?://\S+")
_MD_DECORATORS = re.compile(r"[*_~#>]+")
_TABLE_RULE = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$")
_ASCII_NOISE_LINE = re.compile(r"^[\s|+\-=_~`]{4,}$")


def prepare_tts_text(raw: str, max_chars: int) -> str:
    """
    Return safe, bounded plain text for Coqui. Empty string means caller should skip TTS.
    """
    if not raw:
        return ""
    t = _CONTROL_CHARS.sub(" ", raw)
    t = _FENCED_CODE_BLOCK.sub(" ", t)
    t = _MARKDOWN_LINK.sub(r"\1", t)
    t = _INLINE_CODE.sub(r"\1", t)
    t = _URL.sub(" ", t)
    t = t.replace("\t", " ")
    clean_lines: list[str] = []
    for line in t.splitlines():
        ln = line.strip()
        if not ln:
            continue
        if _TABLE_RULE.match(ln) or _ASCII_NOISE_LINE.match(ln):
            continue
        # Drop table pipes/decorators so spoken text is natural.
        ln = ln.replace("|", " ")
        ln = _MD_DECORATORS.sub("", ln)
        clean_lines.append(ln)
    t = " ".join(clean_lines)
    t = _EMOJI_AND_SYMBOLS.sub(" ", t)
    # LJSpeech / ASCII vocabs: map smart quotes and dashes to reduce "not in vocabulary" drops.
    t = (
        t.replace("\u2019", "'")
        .replace("\u2018", "'")
        .replace("\u201c", '"')
        .replace("\u201d", '"')
        .replace("\u2014", "-")
        .replace("\u2013", "-")
    )
    t = _MULTI_SPACE.sub(" ", t).strip(" .-")
    if not t:
        return ""
    if len(t) > max_chars:
        t = t[: max(0, max_chars - 1)].rstrip() + "…"
    return t
