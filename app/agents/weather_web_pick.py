"""Pick the best DuckDuckGo row for weather context (keyword scoring over title + body)."""

from __future__ import annotations

WEATHER_SCORE_KEYS = (
    "weather",
    "temperature",
    "forecast",
    "rain",
    "humidity",
    "wind",
    "dhaka",
)


def select_weather_web_result(
    web_results: list[dict[str, str]],
) -> dict[str, str] | None:
    """Return the snippet with the highest keyword overlap, or the first row if all scores tie at 0."""
    if not web_results:
        return None
    best: tuple[int, dict[str, str]] | None = None
    for item in web_results:
        hay = f"{item.get('title', '')} {item.get('body', '')}".lower()
        score = sum(1 for key in WEATHER_SCORE_KEYS if key in hay)
        if best is None or score > best[0]:
            best = (score, item)
    return best[1] if best else web_results[0]
