from __future__ import annotations

import asyncio

from duckduckgo_search import DDGS

from app.core.settings import get_settings


settings = get_settings()


class DuckDuckGoSearchClient:
    """Async wrapper around DuckDuckGo search."""

    async def search(self, query: str, *, max_results: int | None = None) -> list[dict[str, str]]:
        limit = max_results or settings.duckduckgo_max_results
        return await asyncio.to_thread(self._search_sync, query, limit)

    def _search_sync(self, query: str, max_results: int) -> list[dict[str, str]]:
        with DDGS() as ddgs:
            results = ddgs.text(
                keywords=query,
                region=settings.duckduckgo_region,
                safesearch=settings.duckduckgo_safesearch,
                timelimit=settings.duckduckgo_time_limit,
                max_results=max_results,
            )
            return [
                {
                    "title": item.get("title", ""),
                    "href": item.get("href", ""),
                    "body": item.get("body", ""),
                }
                for item in results
            ]
