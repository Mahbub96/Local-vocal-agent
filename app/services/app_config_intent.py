"""Natural-language commands to change per-user assistant settings (chat + voice)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from app.services.effective_assistant_prefs import (
    apply_assistant_override_updates,
    resolve_effective_assistant_prefs,
)


@dataclass(frozen=True, slots=True)
class AppConfigOutcome:
    """Result of interpreting a message for assistant configuration."""

    merged_profile: dict[str, Any] | None
    profile_changed: bool
    stripped_query: str
    """Text left for the LLM after removing configuration phrases."""
    skip_llm: bool
    """If True, respond with ``direct_reply`` only (no model call)."""
    direct_reply: str | None
    confirmation_note: str | None
    """When both config and a normal query run, prepend this to the model reply."""


# --- Whole-message intents (checked on original text) ---

_SHOW = re.compile(
    r"(?i)^\s*(?:what\s+are|show|list|display|tell\s+me)\s+(?:my\s+)?(?:current\s+)?(?:assistant|app)\s+"
    r"(?:settings|configuration|prefs|preferences|options)\s*[.!?\s]*$"
)

_RESET = re.compile(
    r"(?i)^\s*(?:reset|clear|restore)\s+(?:my\s+)?(?:assistant|app)\s+"
    r"(?:settings|configuration|overrides|prefs)\s*(?:to\s+default(?:s)?)?\s*[.!?\s]*$"
)

_HELP = re.compile(
    r"(?i)^\s*(?:how\s+do\s+i|how\s+can\s+i)\s+configure\s+(?:this\s+)?(?:app|assistant)\s*[.!?\s]*$"
)
_HARDEN_ALL = re.compile(
    r"(?i)^\s*(?:reconfigure|configure|set\s+up)\s+(?:everything|all)\b.*"
)


def _trim_leading_junk(stripped: str) -> str:
    """After removing config clauses, drop leading punctuation/whitespace."""
    t = stripped.strip()
    return re.sub(r"^[.!?,;:\"'\s]+", "", t).strip()


def _strip_spans(text: str, spans: list[tuple[int, int]]) -> str:
    if not spans:
        return text.strip()
    out: list[str] = []
    cursor = 0
    for start, end in sorted(spans):
        if start > cursor:
            out.append(text[cursor:start])
        cursor = max(cursor, end)
    out.append(text[cursor:])
    return " ".join(" ".join(s.split()) for s in out if s).strip()


# Key-specific patterns: (setting_key, regex, group_index_for_int_or_none_for_bool)
_PATTERNS_INT: list[tuple[str, re.Pattern[str], int]] = [
    (
        "memory_top_k",
        re.compile(
            r"(?i)(?:^|[.!?\n]\s*)(?:set|change|put|use)\s+(?:the\s+)?(?:memory|semantic|vector)\s+"
            r"(?:top[\s_-]?k|retrieval|recall)\s*(?:to|at|is|=|:)?\s*(\d{1,3})\b"
        ),
        1,
    ),
    (
        "memory_top_k",
        re.compile(
            r"(?i)(?:^|[.!?\n]\s*)(?:retrieve|fetch|use)\s+(\d{1,3})\s+"
            r"(?:memory|semantic|vector)?\s*(?:rows|hits|results|matches|memories)\b"
        ),
        1,
    ),
    (
        "short_term_message_limit",
        re.compile(
            r"(?i)(?:^|[.!?\n]\s*)(?:set|change)\s+(?:the\s+)?(?:short[\s-]?term|recent)\s+"
            r"(?:message|conversation)\s+limit\s*(?:to|at|is|=)?\s*(\d{1,3})\b"
        ),
        1,
    ),
    (
        "short_term_message_limit",
        re.compile(
            r"(?i)(?:^|[.!?\n]\s*)keep\s+(?:only\s+)?(?:the\s+)?last\s+(\d{1,3})\s+"
            r"(?:messages?|turns?)\s+(?:in\s+)?(?:context|history)\b"
        ),
        1,
    ),
    (
        "memory_keyword_match_limit",
        re.compile(
            r"(?i)(?:^|[.!?\n]\s*)(?:set|change)\s+keyword\s+(?:memory\s+)?(?:match\s+)?limit\s*"
            r"(?:to|at|is|=)?\s*(\d{1,3})\b"
        ),
        1,
    ),
    (
        "memory_injected_chars_per_message",
        re.compile(
            r"(?i)(?:^|[.!?\n]\s*)(?:set|change)\s+(?:memory\s+)?(?:excerpt|snippet|line)\s+"
            r"(?:length|limit|size)\s*(?:to|at|is|=)?\s*(\d{3,5})\b"
        ),
        1,
    ),
    (
        "ollama_num_ctx",
        re.compile(
            r"(?i)(?:^|[.!?\n]\s*)(?:set|change|use)\s+(?:llm\s+)?(?:context|context\s+window)\s*"
            r"(?:to|at|is|=)?\s*(\d{3,6})\b"
        ),
        1,
    ),
    (
        "ollama_num_predict",
        re.compile(
            r"(?i)(?:^|[.!?\n]\s*)(?:set|change|use)\s+(?:max\s+)?(?:reply\s+)?(?:tokens?|length)\s*"
            r"(?:to|at|is|=)?\s*(-?\d{1,5})\b"
        ),
        1,
    ),
    (
        "ollama_num_predict",
        re.compile(
            r"(?i)(?:^|[.!?\n]\s*)(?:cap|limit)\s+(?:responses?\s+)?(?:at|to)\s+(\d{1,5})\s+tokens?\b"
        ),
        1,
    ),
]

_TEMP_FLOAT = re.compile(
    r"(?i)(?:^|[.!?\n]\s*)(?:set|change)\s+(?:llm\s+)?temperature\s*(?:to|at|is|=)?\s*"
    r"([0-9]+(?:\.[0-9]+)?)\b"
)

_BOOL_ON = re.compile(
    r"(?i)(?:^|[.!?\n]\s*)(?:turn|switch)\s+on\s+(?:the\s+)?(?:keyword|sqlite)\s+memory\s+supplement\b"
)
_BOOL_OFF = re.compile(
    r"(?i)(?:^|[.!?\n]\s*)(?:turn|switch)\s+off\s+(?:the\s+)?(?:keyword|sqlite)\s+memory\s+supplement\b"
)
_SEARCH_OFF = re.compile(
    r"(?i)(?:^|[.!?\n]\s*)(?:disable|turn\s+off)\s+(?:auto\s+)?(?:web\s+)?search\s+"
    r"when\s+(?:there\s+is\s+)?no\s+memory\b"
)
_SEARCH_ON = re.compile(
    r"(?i)(?:^|[.!?\n]\s*)(?:enable|turn\s+on)\s+(?:auto\s+)?(?:web\s+)?search\s+"
    r"when\s+(?:there\s+is\s+)?no\s+memory\b"
)
_ALWAYS_WEB_ON = re.compile(
    r"(?i)(?:^|[.!?\n]\s*)(?:enable|turn\s+on|always\s+use)\s+(?:internet|web)\s+search\b"
)
_ALWAYS_WEB_OFF = re.compile(
    r"(?i)(?:^|[.!?\n]\s*)(?:disable|turn\s+off)\s+(?:always\s+)?(?:internet|web)\s+search\b"
)
_STRICT_NO_GUESS_ON = re.compile(
    r"(?i)(?:^|[.!?\n]\s*)(?:enable|turn\s+on)\s+(?:strict\s+)?(?:no[-\s]?guess|factual)\s+mode\b"
)
_STRICT_NO_GUESS_OFF = re.compile(
    r"(?i)(?:^|[.!?\n]\s*)(?:disable|turn\s+off)\s+(?:strict\s+)?(?:no[-\s]?guess|factual)\s+mode\b"
)
_FORMAT_TABLE = re.compile(
    r"(?i)(?:^|[.!?\n]\s*)(?:prefer|use|set)\s+(?:response\s+)?format\s+(?:to\s+)?table\b"
)
_FORMAT_MARKDOWN = re.compile(
    r"(?i)(?:^|[.!?\n]\s*)(?:prefer|use|set)\s+(?:response\s+)?format\s+(?:to\s+)?markdown\b"
)
_FORMAT_PLAIN = re.compile(
    r"(?i)(?:^|[.!?\n]\s*)(?:prefer|use|set)\s+(?:response\s+)?format\s+(?:to\s+)?plain(?:\s+text)?\b"
)
_FORMAT_AUTO = re.compile(
    r"(?i)(?:^|[.!?\n]\s*)(?:reset|use)\s+(?:response\s+)?format\s+(?:to\s+)?auto\b"
)

_DEFAULT_TOPK = re.compile(
    r"(?i)(?:^|[.!?\n]\s*)(?:use\s+default|reset)\s+(?:for\s+)?(?:memory\s+)?(?:top[\s_-]?k|retrieval)\b"
)


def _format_overview(profile: dict[str, Any]) -> str:
    p = resolve_effective_assistant_prefs(profile)
    raw_ov = profile.get("assistant_app_overrides")
    ov_note = ""
    if isinstance(raw_ov, dict) and raw_ov:
        ov_note = f" ({len(raw_ov)} field(s) differ from server defaults)"
    lines = [
        f"Here are your effective assistant settings{ov_note}:",
        f"- Memory retrieval (top_k): {p.memory_top_k}",
        f"- Recent conversation messages in context: {p.short_term_message_limit}",
        f"- Keyword memory supplement: {'on' if p.memory_keyword_supplement else 'off'}",
        f"- Keyword match limit: {p.memory_keyword_match_limit}",
        f"- Memory line length (chars per retrieved message): {p.memory_injected_chars_per_message}",
        f"- Auto web search when memory is empty: {'on' if p.assistant_search_if_no_memory else 'off'}",
        f"- LLM context window (num_ctx): {p.ollama_num_ctx}",
        f"- Max reply tokens (num_predict): {p.ollama_num_predict}",
        f"- LLM temperature: {p.ollama_temperature:.2f}",
        f"- Always web search: {'on' if p.always_web_search else 'off'}",
        f"- Strict no-guessing mode: {'on' if p.strict_no_guessing else 'off'}",
        f"- Preferred response format: {p.response_format_preference}",
        "",
        "Say things like “set memory top k to 24”, “disable auto web search when memory is empty”, "
        "or “reset assistant settings” to change these. Speech speed and wake name still use voice phrases.",
    ]
    return "\n".join(lines)


def _help_text() -> str:
    return (
        "You can configure this assistant by chat or voice. Examples:\n"
        "- “Set memory top k to 20” — how many semantic memory rows to retrieve.\n"
        "- “Set short term message limit to 12” — recent turns in the prompt.\n"
        "- “Turn off keyword memory supplement” / “turn it back on”.\n"
        "- “Disable auto web search when memory is empty” (or enable).\n"
        "- “Set context window to 8192” or “set max reply tokens to 512”.\n"
        "- “Set LLM temperature to 0.3”.\n"
        "- “Enable always web search” / “turn it off”.\n"
        "- “Enable strict no-guessing mode” / “disable factual mode”.\n"
        "- “Set response format to table/markdown/plain/auto”.\n"
        "- “Reconfigure everything” — one-shot hardened defaults.\n"
        "- “Show my assistant settings” or “reset assistant settings”.\n"
        "TTS speed and wake/silent mode still use phrases like “speak faster” or “wake word is …”."
    )


def process_app_configuration_message(
    profile: dict[str, Any],
    message: str,
) -> AppConfigOutcome:
    """
    Parse configuration commands, merge into ``assistant_app_overrides``, strip matched spans.

    Voice and chat share the same path; regexes are tuned for short spoken English.
    """
    text = message.strip()
    if not text:
        return AppConfigOutcome(None, False, "", False, None, None)

    if _HELP.match(text):
        return AppConfigOutcome(None, False, "", True, _help_text(), None)

    if _SHOW.match(text):
        return AppConfigOutcome(None, False, "", True, _format_overview(profile), None)

    if _HARDEN_ALL.match(text):
        merged = apply_assistant_override_updates(
            profile,
            {
                "always_web_search": True,
                "strict_no_guessing": True,
                "response_format_preference": "markdown",
                "assistant_search_if_no_memory": True,
            },
            remove_keys=[],
        )
        return AppConfigOutcome(
            merged,
            True,
            "",
            True,
            (
                "Done. I hardened the assistant defaults for this user: always web search ON, "
                "strict no-guessing ON, markdown responses ON, and auto web search when memory is empty ON."
            ),
            None,
        )

    updates: dict[str, Any] = {}
    remove_keys: list[str] = []
    spans: list[tuple[int, int]] = []

    if _RESET.match(text):
        merged = dict(profile)
        merged.pop("assistant_app_overrides", None)
        return AppConfigOutcome(
            merged,
            True,
            "",
            True,
            "Assistant settings restored to server defaults for your profile.",
            None,
        )

    # Integer / float patterns
    for key, rx, _ in _PATTERNS_INT:
        m = rx.search(text)
        if m:
            spans.append((m.start(), m.end()))
            try:
                v = int(m.group(1))
            except (IndexError, ValueError):
                continue
            updates[key] = v

    tm = _TEMP_FLOAT.search(text)
    if tm:
        spans.append((tm.start(), tm.end()))
        try:
            updates["ollama_temperature"] = float(tm.group(1))
        except ValueError:
            pass

    b_on = _BOOL_ON.search(text)
    if b_on:
        spans.append((b_on.start(), b_on.end()))
        updates["memory_keyword_supplement"] = True
    b_off = _BOOL_OFF.search(text)
    if b_off:
        spans.append((b_off.start(), b_off.end()))
        updates["memory_keyword_supplement"] = False

    m = _SEARCH_OFF.search(text)
    if m:
        spans.append((m.start(), m.end()))
        updates["assistant_search_if_no_memory"] = False
    m = _SEARCH_ON.search(text)
    if m:
        spans.append((m.start(), m.end()))
        updates["assistant_search_if_no_memory"] = True
    m = _ALWAYS_WEB_ON.search(text)
    if m:
        spans.append((m.start(), m.end()))
        updates["always_web_search"] = True
    m = _ALWAYS_WEB_OFF.search(text)
    if m:
        spans.append((m.start(), m.end()))
        updates["always_web_search"] = False
    m = _STRICT_NO_GUESS_ON.search(text)
    if m:
        spans.append((m.start(), m.end()))
        updates["strict_no_guessing"] = True
    m = _STRICT_NO_GUESS_OFF.search(text)
    if m:
        spans.append((m.start(), m.end()))
        updates["strict_no_guessing"] = False
    m = _FORMAT_TABLE.search(text)
    if m:
        spans.append((m.start(), m.end()))
        updates["response_format_preference"] = "table"
    m = _FORMAT_MARKDOWN.search(text)
    if m:
        spans.append((m.start(), m.end()))
        updates["response_format_preference"] = "markdown"
    m = _FORMAT_PLAIN.search(text)
    if m:
        spans.append((m.start(), m.end()))
        updates["response_format_preference"] = "plain"
    m = _FORMAT_AUTO.search(text)
    if m:
        spans.append((m.start(), m.end()))
        updates["response_format_preference"] = "auto"

    m = _DEFAULT_TOPK.search(text)
    if m:
        spans.append((m.start(), m.end()))
        remove_keys.append("memory_top_k")

    if updates or remove_keys:
        stripped = _trim_leading_junk(_strip_spans(text, spans))
        merged = apply_assistant_override_updates(profile, updates, remove_keys=remove_keys)
        confirms = _human_confirm_lines(updates, remove_keys)
        body = "Updated your assistant configuration: " + "; ".join(confirms) + "." if confirms else ""
        if not stripped:
            reply = body if body else None
            return AppConfigOutcome(
                merged,
                True,
                "",
                True,
                reply or "No configuration changes detected.",
                None,
            )
        return AppConfigOutcome(merged, True, stripped, False, None, body or None)

    return AppConfigOutcome(None, False, text, False, None, None)


def _human_confirm_lines(updates: dict[str, Any], remove_keys: list[str]) -> list[str]:
    lines: list[str] = []
    label = {
        "memory_top_k": "memory top_k",
        "short_term_message_limit": "short-term message limit",
        "memory_keyword_match_limit": "keyword match limit",
        "memory_injected_chars_per_message": "memory line length",
        "memory_keyword_supplement": "keyword memory supplement",
        "assistant_search_if_no_memory": "auto web search when memory is empty",
        "always_web_search": "always web search",
        "strict_no_guessing": "strict no-guessing mode",
        "response_format_preference": "response format",
        "ollama_num_ctx": "LLM context window",
        "ollama_num_predict": "max reply tokens",
        "ollama_temperature": "LLM temperature",
    }
    for k, v in updates.items():
        if k == "memory_keyword_supplement":
            lines.append(f"{label.get(k, k)} → {'on' if v else 'off'}")
        elif k == "assistant_search_if_no_memory":
            lines.append(f"{label.get(k, k)} → {'on' if v else 'off'}")
        else:
            lines.append(f"{label.get(k, k)} → {v}")
    for k in remove_keys:
        lines.append(f"{label.get(k, k)} → default")
    return lines
