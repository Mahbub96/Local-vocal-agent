"""Minimal post-LLM cleanup: strip robotic *openings* and banned Bangla *tail* phrases.

Tone is controlled in ``prompt_builder``—this module only removes known bad patterns.
"""

from __future__ import annotations

import re

from app.agents.language_detection import ResponseLanguageTarget

_ROBOTIC_EN_LEAD = re.compile(
    r"^\s*("
    r"certainly[!.,\s]*|"
    r"of course[!.,\s]*|"
    r"i'?d be (?:happy|delighted|glad) to\b[^.!?]*[.!?]\s*|"
    r"as an ai\b[^.!?]*[.!?]\s*|"
    r"as a language model\b[^.!?]*[.!?]\s*|"
    r"great question[!.,\s]*|"
    r"that'?s a great question[!.,\s]*|"
    r"in conclusion\b[^.!?]*[.!?]\s*|"
    r"in summary\b[^.!?]*[.!?]\s*|"
    r"to summarize\b[^.!?]*[.!?]\s*"
    r")+",
    re.IGNORECASE | re.DOTALL,
)

_ROBOTIC_BN_LEAD = re.compile(
    r"^\s*(নিঃসন্দেহে|অবশ্যই|নিশ্চিতভাবে)[।!\s,]+",
)

# Model sometimes appends rude “say it clearer” closings despite prompt bans—strip from the end only.
_PATRONIZING_BN_TAIL = re.compile(
    r"\s+(?:আমার\s+খুব\s+|এটা\s+)?ভালো\s+করে\s+বলতে\s+পারেন\s+না\s+তো[।.!?…\s]*$",
    re.UNICODE,
)

# Leading fluff only — do not strip mid-text (preserves meaning).
_GENERIC_AI_OPENERS_EN = re.compile(
    r"^\s*("
    r"as an ai assistant[,.\s]*|"
    r"i'?m (?:an |your )?ai (?:assistant|language model)[^.!?]*[.!?]\s*|"
    r"i can help you(?:\s+with that)?[,.\s]*|"
    r"i'?d be (?:happy|glad) to help(?:\s+you)?(?:\s+with that)?[,.\s]*|"
    r"here(?:'s| is) what i (?:can|know)[^.!?]*[.!?]\s*"
    r")+",
    re.IGNORECASE | re.DOTALL,
)


def remove_patronizing_bangla_tail(text: str) -> str:
    """Remove trailing patronizing clarification phrases (Bangla); preserve the rest."""
    t = (text or "").strip()
    if not t:
        return t
    for _ in range(4):
        t2 = _PATRONIZING_BN_TAIL.sub("", t).strip()
        if t2 == t or not t2:
            break
        t = t2
    return t


def remove_generic_ai_openers(text: str) -> str:
    """Strip generic capability / AI-role openers at the start only."""
    t = (text or "").strip()
    if not t:
        return t
    prev = None
    while prev != t:
        prev = t
        t = _GENERIC_AI_OPENERS_EN.sub("", t).strip()
    return t


def humanize_response(
    text: str,
    *,
    target: ResponseLanguageTarget,
) -> str:
    """Strip generic AI openers, robotic leads (by target), patronizing Bangla tail when applicable; collapse spaces."""
    t = (text or "").strip()
    if not t:
        return t

    t = remove_generic_ai_openers(t)

    if target in (ResponseLanguageTarget.ENGLISH, ResponseLanguageTarget.BANGLISH):
        t = _ROBOTIC_EN_LEAD.sub("", t).strip()

    if target in (ResponseLanguageTarget.BENGALI_SCRIPT, ResponseLanguageTarget.BANGLISH):
        t = _ROBOTIC_BN_LEAD.sub("", t).strip()
        t = remove_patronizing_bangla_tail(t)

    t = re.sub(r"[ \t]{2,}", " ", t)
    return t.strip()
