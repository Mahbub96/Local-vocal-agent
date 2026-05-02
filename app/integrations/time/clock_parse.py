"""Parse wall-clock strings from formatted LIVE TIME lines (no HTTP)."""

from __future__ import annotations

import re


def extract_iso_clock_from_time_line(time_line: str) -> str | None:
    """Pull 'YYYY-MM-DD HH:MM:SS' from our formatted LIVE TIME line for safe substitution."""
    m = re.search(r":\s*(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\b", time_line)
    return m.group(1) if m else None
