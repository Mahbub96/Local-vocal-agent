"""Post-LLM cleanup for time placeholders, compact time/date lines, and internet-claim fixes."""

from __future__ import annotations

import re
from datetime import datetime

from app.integrations.time.clock_parse import extract_iso_clock_from_time_line


def _zone_label_from_time_line(time_line: str) -> str:
    zone_match = re.search(r"for ([^:]+):", time_line)
    return zone_match.group(1).strip() if zone_match else "your location"


def compact_time_response(time_line: str | None) -> str | None:
    """One-line user-facing time string from a LIVE TIME line."""
    if not time_line:
        return None
    clock = extract_iso_clock_from_time_line(time_line)
    if not clock:
        return time_line
    zone = _zone_label_from_time_line(time_line)
    return f"Current local time in {zone}: {clock}."


def compact_date_response(time_line: str | None) -> str | None:
    """One-line date string derived from the clock embedded in a LIVE TIME line."""
    if not time_line:
        return None
    clock = extract_iso_clock_from_time_line(time_line)
    if not clock:
        return None
    try:
        dt = datetime.strptime(clock, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None
    zone = _zone_label_from_time_line(time_line)
    return f"Today's date in {zone} is {dt.date().isoformat()}."

# Models sometimes echo training-style templates; strip even when a live time was provided.
LLM_TIME_PLACEHOLDER = re.compile(
    r"\[?\s*insert (?:the )?current time here\s*\]?|"
    r"\[insert[^\]\n]{0,60}time[^\]\n]{0,30}here\s*\]|"
    r"\[TBD\]",
    re.IGNORECASE,
)

NO_INTERNET_CLAIM = re.compile(
    r"(?i)\b(i\s+(?:do not|don't)\s+have\s+(?:real[- ]?time\s+)?internet\s+access|"
    r"simulated\s+environment|cannot\s+browse\s+the\s+internet)\b"
)

_FALLBACK_NO_TIME = (
    "a live time service was unreachable—Bangladesh (Asia/Dhaka) is UTC+6 (year-round)"
)
_REPLACEMENT_WITH_WEB = "I have live internet access for this query"


def strip_llm_time_placeholders(response: str, time_line: str | None) -> str:
    """Replace bracket/insert time templates with a real clock or a fixed fallback."""
    if time_line:
        clock = extract_iso_clock_from_time_line(time_line) or time_line
        return LLM_TIME_PLACEHOLDER.sub(clock, response).strip()
    return LLM_TIME_PLACEHOLDER.sub(_FALLBACK_NO_TIME, response).strip()


def sanitize_live_data_claims(response: str, *, used_internet: bool) -> str:
    """If we used the web, remove 'I don't have internet' style contradictions."""
    if not used_internet:
        return response
    cleaned = NO_INTERNET_CLAIM.sub(_REPLACEMENT_WITH_WEB, response)
    return cleaned.strip()
