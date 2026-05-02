"""Merge server defaults from Settings with per-user ``assistant_app_overrides`` on the profile."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.core.settings import Settings, get_settings


@dataclass(frozen=True, slots=True)
class EffectiveAssistantPrefs:
    memory_top_k: int
    short_term_message_limit: int
    memory_keyword_supplement: bool
    memory_keyword_match_limit: int
    memory_injected_chars_per_message: int
    assistant_search_if_no_memory: bool
    ollama_num_ctx: int
    ollama_num_predict: int
    ollama_temperature: float
    always_web_search: bool
    strict_no_guessing: bool
    response_format_preference: str


def _coerce_int(raw: Any, *, fallback: int, lo: int, hi: int) -> int:
    try:
        v = int(raw)
    except (TypeError, ValueError):
        return fallback
    return max(lo, min(hi, v))


def _coerce_bool(raw: Any, *, fallback: bool) -> bool:
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, (int, float)):
        return bool(raw)
    if isinstance(raw, str):
        s = raw.strip().lower()
        if s in ("1", "true", "yes", "on"):
            return True
        if s in ("0", "false", "no", "off"):
            return False
    return fallback


def _coerce_float(raw: Any, *, fallback: float, lo: float, hi: float) -> float:
    try:
        v = float(raw)
    except (TypeError, ValueError):
        return fallback
    return max(lo, min(hi, v))


def resolve_effective_assistant_prefs(
    profile: dict[str, Any] | None,
    *,
    base: Settings | None = None,
) -> EffectiveAssistantPrefs:
    """Resolve knobs the user may override via chat/voice (stored under ``assistant_app_overrides``)."""
    s = base or get_settings()
    overrides: dict[str, Any] = {}
    if profile:
        raw = profile.get("assistant_app_overrides")
        if isinstance(raw, dict):
            overrides = raw

    return EffectiveAssistantPrefs(
        memory_top_k=_coerce_int(
            overrides.get("memory_top_k", s.memory_top_k),
            fallback=s.memory_top_k,
            lo=1,
            hi=100,
        ),
        short_term_message_limit=_coerce_int(
            overrides.get("short_term_message_limit", s.short_term_message_limit),
            fallback=s.short_term_message_limit,
            lo=4,
            hi=80,
        ),
        memory_keyword_supplement=_coerce_bool(
            overrides.get("memory_keyword_supplement", s.memory_keyword_supplement),
            fallback=s.memory_keyword_supplement,
        ),
        memory_keyword_match_limit=_coerce_int(
            overrides.get("memory_keyword_match_limit", s.memory_keyword_match_limit),
            fallback=s.memory_keyword_match_limit,
            lo=0,
            hi=100,
        ),
        memory_injected_chars_per_message=_coerce_int(
            overrides.get("memory_injected_chars_per_message", s.memory_injected_chars_per_message),
            fallback=s.memory_injected_chars_per_message,
            lo=200,
            hi=16_000,
        ),
        assistant_search_if_no_memory=_coerce_bool(
            overrides.get("assistant_search_if_no_memory", s.assistant_search_if_no_memory),
            fallback=s.assistant_search_if_no_memory,
        ),
        ollama_num_ctx=_coerce_int(
            overrides.get("ollama_num_ctx", s.ollama_num_ctx),
            fallback=s.ollama_num_ctx,
            lo=512,
            hi=131_072,
        ),
        ollama_num_predict=_coerce_int(
            overrides.get("ollama_num_predict", s.ollama_num_predict),
            fallback=s.ollama_num_predict,
            lo=-1,
            hi=32_768,
        ),
        ollama_temperature=_coerce_float(
            overrides.get("ollama_temperature", s.ollama_temperature),
            fallback=s.ollama_temperature,
            lo=0.0,
            hi=2.0,
        ),
        always_web_search=_coerce_bool(
            overrides.get("always_web_search", True),
            fallback=True,
        ),
        strict_no_guessing=_coerce_bool(
            overrides.get("strict_no_guessing", True),
            fallback=True,
        ),
        response_format_preference=(
            str(overrides.get("response_format_preference", "auto")).strip().lower()
            if str(overrides.get("response_format_preference", "auto")).strip().lower()
            in {"auto", "table", "markdown", "plain"}
            else "auto"
        ),
    )


def apply_assistant_override_updates(
    existing_profile: dict[str, Any],
    updates: dict[str, Any],
    *,
    remove_keys: list[str] | None = None,
) -> dict[str, Any]:
    """Return a profile dict copy with merged ``assistant_app_overrides``."""
    merged = dict(existing_profile)
    bucket: dict[str, Any] = {}
    prev = merged.get("assistant_app_overrides")
    if isinstance(prev, dict):
        bucket = dict(prev)
    for k in remove_keys or []:
        bucket.pop(k, None)
    for key, val in updates.items():
        if val is None:
            bucket.pop(key, None)
        else:
            bucket[key] = val
    if bucket:
        merged["assistant_app_overrides"] = bucket
    else:
        merged.pop("assistant_app_overrides", None)
    return merged
