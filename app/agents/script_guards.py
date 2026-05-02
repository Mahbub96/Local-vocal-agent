"""Script detection and output policy per response language target.

- **BENGALI_SCRIPT:** only Bengali script + common punctuation/numbers; no Arabic, Devanagari, CJK.
- **ENGLISH:** Latin-heavy output; stray non-Latin scripts are stripped (not replaced with apology
  unless the result is empty).
- **BANGLISH:** Bengali + Latin allowed together; other scripts stripped if they appear by mistake.

``task_type`` (from :mod:`app.agents.task_policy`) selects strict vs conversational buckets via
``apply_voice_mode(task_type)``: strict tasks keep the hard Bangla-script rule; conversational
tasks may strip stray characters instead of replacing the whole reply when possible.
Bangla-profile **input** script rejection (Arabic/CJK in the user message) is handled in
``assistant_agent`` and only relaxes for ``apply_voice_mode(task_type) and voice_turn``.
"""

from __future__ import annotations

from app.agents.language_detection import ResponseLanguageTarget
from app.agents.task_policy import TaskType, apply_voice_mode


def contains_arabic_script(text: str) -> bool:
    return any(
        ("\u0600" <= ch <= "\u06ff")
        or ("\u0750" <= ch <= "\u077f")
        or ("\u08a0" <= ch <= "\u08ff")
        or ("\ufb50" <= ch <= "\ufdff")
        or ("\ufe70" <= ch <= "\ufeff")
        for ch in text
    )


def contains_cjk_script(text: str) -> bool:
    return any(
        ("\u3040" <= ch <= "\u30ff")
        or ("\u31f0" <= ch <= "\u31ff")
        or ("\u4e00" <= ch <= "\u9fff")
        or ("\u3400" <= ch <= "\u4dbf")
        or ("\u1100" <= ch <= "\u11ff")
        or ("\u3130" <= ch <= "\u318f")
        or ("\ua960" <= ch <= "\ua97f")
        or ("\uac00" <= ch <= "\ud7af")
        or ("\ud7b0" <= ch <= "\ud7ff")
        for ch in text
    )


def contains_devanagari_script(text: str) -> bool:
    return any("\u0900" <= ch <= "\u097f" for ch in text)


def contains_forbidden_non_bangla_script(text: str) -> bool:
    return (
        contains_arabic_script(text)
        or contains_cjk_script(text)
        or contains_devanagari_script(text)
    )


def strip_forbidden_scripts(text: str) -> str:
    out: list[str] = []
    for ch in text:
        if (
            ("\u0600" <= ch <= "\u06ff")
            or ("\u0750" <= ch <= "\u077f")
            or ("\u08a0" <= ch <= "\u08ff")
            or ("\ufb50" <= ch <= "\ufdff")
            or ("\ufe70" <= ch <= "\ufeff")
            or ("\u3040" <= ch <= "\u30ff")
            or ("\u31f0" <= ch <= "\u31ff")
            or ("\u4e00" <= ch <= "\u9fff")
            or ("\u3400" <= ch <= "\u4dbf")
            or ("\u1100" <= ch <= "\u11ff")
            or ("\u3130" <= ch <= "\u318f")
            or ("\ua960" <= ch <= "\ua97f")
            or ("\uac00" <= ch <= "\ud7af")
            or ("\ud7b0" <= ch <= "\ud7ff")
            or ("\u0900" <= ch <= "\u097f")
        ):
            continue
        out.append(ch)
    return "".join(out)


_BN_SCRIPT_FALLBACK = (
    "আমি দুঃখিত, আউটপুটে ভুল স্ক্রিপ্ট চলে এসেছে। অনুগ্রহ করে আবার বাংলায় বলুন বা লিখুন।"
)
_MIXED_SCRIPT_FALLBACK = (
    "আউটপুটে অন্য লিপি ঢুকে গেছে—আবার একবার বলবেন? বা ছোট করে ইংরেজিতে লিখুন।"
)


def apply_script_policy(
    response: str,
    target: ResponseLanguageTarget,
    task_type: TaskType | None = None,
    *,
    input_source: str = "text",
) -> str:
    """
    Apply script rules after generation.

    ``input_source`` ``\"voice\"``: never replace the reply with script-error fallbacks—strip silently
    or keep the original text so voice turns never break into correction messages.

    If ``task_type`` is None or not a voice-relaxed task (and not voice input), behavior matches strict policy.
    """
    if not response.strip():
        return response

    strict = task_type is None or not apply_voice_mode(task_type)
    voice_out = input_source == "voice"

    if voice_out:
        if not contains_forbidden_non_bangla_script(response):
            return response
        cleaned = strip_forbidden_scripts(response).strip()
        return cleaned if cleaned else response

    if target == ResponseLanguageTarget.BENGALI_SCRIPT:
        if not contains_forbidden_non_bangla_script(response):
            return response
        if strict:
            return _BN_SCRIPT_FALLBACK
        cleaned = strip_forbidden_scripts(response).strip()
        if len(cleaned) >= 8:
            return cleaned
        return _BN_SCRIPT_FALLBACK

    if not contains_forbidden_non_bangla_script(response):
        return response

    cleaned = strip_forbidden_scripts(response).strip()
    if cleaned:
        return cleaned
    if target == ResponseLanguageTarget.BANGLISH:
        return _MIXED_SCRIPT_FALLBACK
    return "Sorry — the reply had unexpected characters. Please try again."
