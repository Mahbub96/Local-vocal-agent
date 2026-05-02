"""Time integrations: ``clock_parse`` is httpx-free; ``world_time`` loads httpx lazily."""

from __future__ import annotations

from typing import Any

from app.integrations.time.clock_parse import extract_iso_clock_from_time_line

__all__ = [
    "extract_iso_clock_from_time_line",
    "fetch_local_time_utc_string",
    "refine_search_query_for_tool",
    "resolve_timezone_for_query",
]


def __getattr__(name: str) -> Any:
    if name == "fetch_local_time_utc_string":
        from app.integrations.time.world_time import fetch_local_time_utc_string

        return fetch_local_time_utc_string
    if name == "refine_search_query_for_tool":
        from app.integrations.time.world_time import refine_search_query_for_tool

        return refine_search_query_for_tool
    if name == "resolve_timezone_for_query":
        from app.integrations.time.world_time import resolve_timezone_for_query

        return resolve_timezone_for_query
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
