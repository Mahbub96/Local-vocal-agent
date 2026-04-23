"""Real current time from worldtimeapi.org (no API key)."""

from __future__ import annotations

import logging
import re
from typing import Final

import httpx

logger = logging.getLogger(__name__)

# (user-text pattern, IANA zone for worldtimeapi). Include "bangladeshi" / partial matches.
_ZONE_RULES: Final[tuple[tuple[re.Pattern[str], str], ...]] = (
    (re.compile(r"(?i)bangladesh|bangladeshi|dhaka|\bbst\b|বাংলাদেশ"), "Asia/Dhaka"),
    (re.compile(r"(?i)\bIST\b.*\bindia\b|india.*time|new delhi|mumbai|kolkata"), "Asia/Kolkata"),
    (re.compile(r"(?i)london|uk time|gmt\b.*uk|britain"), "Europe/London"),
    (re.compile(r"(?i)new york|eastern time|us east|nyc\b"), "America/New_York"),
)


def _wants_time(query: str) -> bool:
    return bool(
        re.search(
            r"(?i)\b(time|clock|hour|date|now|today|moment|zone|bst|gmt|ist)\b",
            query,
        )
    )


def resolve_timezone_for_query(query: str) -> str | None:
    if not _wants_time(query):
        return None
    for pattern, zone in _ZONE_RULES:
        if pattern.search(query):
            return zone
    return None


def _format_time_line(tz: str, zone: str, dt: str, off: str, source: str) -> str:
    return (
        f"Official current local time for {tz}: {dt} (offset {off}). "
        f"Source: {source} for IANA zone {zone}."
    )


async def _fetch_worldtimeapi_org(zone: str) -> str | None:
    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            r = await client.get(f"https://worldtimeapi.org/api/timezone/{zone}")
        if r.status_code != 200:
            return None
        data = r.json()
    except Exception as exc:
        logger.debug("worldtimeapi.org failed: %s", exc)
        return None
    raw = (data.get("datetime") or "").replace("T", " ")
    dt = raw[:19] if raw else ""
    if not dt:
        return None
    tz = data.get("timezone") or zone
    off = str(data.get("utc_offset") or data.get("abbreviation") or "")
    return _format_time_line(tz, zone, dt, off, "worldtimeapi.org")


async def _fetch_timeapi_io(zone: str) -> str | None:
    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            r = await client.get(
                "https://timeapi.io/api/Time/current/zone",
                params={"timeZone": zone},
            )
        if r.status_code != 200:
            return None
        data = r.json()
    except Exception as exc:
        logger.debug("timeapi.io request failed: %s", exc)
        return None
    raw = (data.get("dateTime") or data.get("dateTimeTimeZone") or "").replace("T", " ")
    dt = raw[:19] if raw else ""
    if not dt:
        y, mo, d = data.get("year"), data.get("month"), data.get("day")
        h, mi, s = data.get("hour"), data.get("minute"), data.get("seconds")
        if all(v is not None for v in (y, mo, d, h, mi, s)):
            dt = f"{int(y):04d}-{int(mo):02d}-{int(d):02d} {int(h):02d}:{int(mi):02d}:{int(s):02d}"
    if not dt:
        return None
    off = str(data.get("utcOffset") or data.get("utc") or "")
    return _format_time_line(zone, zone, dt, off, "timeapi.io")


async def fetch_local_time_utc_string(zone: str) -> str | None:
    for fetch in (_fetch_worldtimeapi_org, _fetch_timeapi_io):
        try:
            line = await fetch(zone)
        except Exception as exc:
            logger.warning("Time provider failed (%s): %s", fetch.__name__, exc)
            line = None
        if line:
            return line
    logger.warning("All time APIs failed for zone %s", zone)
    return None


def extract_iso_clock_from_time_line(time_line: str) -> str | None:
    """Pull 'YYYY-MM-DD HH:MM:SS' from our formatted LIVE TIME line for safe substitution."""
    m = re.search(r":\s*(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\b", time_line)
    return m.group(1) if m else None


def refine_search_query_for_tool(query: str) -> str:
    """Nudge DuckDuckGo query when the user asks for time in a region."""
    if resolve_timezone_for_query(query) and _wants_time(query):
        if re.search(r"(?i)bangladesh|bangladeshi|dhaka|bst|বাংলাদেশ", query):
            return "current time in Bangladesh right now"
        if re.search(r"(?i)india|delhi|mumbai|kolkata", query):
            return "current time in India now"
    return query.strip()
