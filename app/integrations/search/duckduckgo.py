from __future__ import annotations

import asyncio
from html import unescape
from urllib.parse import quote_plus
from urllib.request import Request, urlopen
import warnings
import xml.etree.ElementTree as ET

try:
    from ddgs import DDGS  # new package name
except Exception:  # pragma: no cover - safe fallback for older environments
    from duckduckgo_search import DDGS  # type: ignore
    warnings.filterwarnings(
        "ignore",
        message="This package (`duckduckgo_search`) has been renamed to `ddgs`!.*",
        category=RuntimeWarning,
    )

from app.core.settings import get_settings


settings = get_settings()


class DuckDuckGoSearchClient:
    """Async wrapper around DuckDuckGo search."""

    async def search(self, query: str, *, max_results: int | None = None) -> list[dict[str, str]]:
        limit = max_results or settings.duckduckgo_max_results
        attempts = max(1, settings.duckduckgo_retry_attempts)
        for attempt in range(attempts):
            try:
                return await asyncio.wait_for(
                    asyncio.to_thread(self._search_sync, query, limit),
                    timeout=settings.duckduckgo_request_timeout,
                )
            except TimeoutError:
                if attempt == attempts - 1:
                    raise
                await asyncio.sleep(0.3 * (2**attempt))
        return []

    def _search_sync(self, query: str, max_results: int) -> list[dict[str, str]]:
        if settings.search_provider == "google":
            google_results = self._google_news_search(query, max_results)
            if google_results:
                return google_results

        with DDGS() as ddgs:
            primary_results = list(
                self._ddgs_text(
                    ddgs,
                    query=query,
                    timelimit=settings.duckduckgo_time_limit,
                    max_results=max_results,
                )
            )
            # Fallback to unrestricted time window when strict real-time filters return nothing.
            # This keeps internet answers useful instead of always returning an empty context.
            if primary_results:
                results = primary_results
            else:
                results = list(
                    self._ddgs_text(
                        ddgs,
                        query=query,
                        timelimit=None,
                        max_results=max_results,
                    )
                )
            if not results:
                results = self._google_news_search(query, max_results)
            return [
                {
                    "title": item.get("title", ""),
                    "href": item.get("href", ""),
                    "body": item.get("body", ""),
                }
                for item in results
            ]

    def _ddgs_text(
        self,
        ddgs: DDGS,
        *,
        query: str,
        timelimit: str | None,
        max_results: int,
    ):
        """Compatibility adapter for ddgs vs duckduckgo_search signatures."""
        common_kwargs = {
            "region": settings.duckduckgo_region,
            "safesearch": settings.duckduckgo_safesearch,
            "timelimit": timelimit,
            "max_results": max_results,
        }
        try:
            return ddgs.text(query=query, **common_kwargs)
        except TypeError:
            return ddgs.text(keywords=query, **common_kwargs)

    def _google_news_search(self, query: str, max_results: int) -> list[dict[str, str]]:
        """Google News RSS query search (no API key required)."""
        lower_query = query.lower()
        if "prothom alo" in lower_query or "prothomalo" in lower_query:
            url = "https://www.prothomalo.com/stories.rss"
        else:
            url = f"https://news.google.com/rss/search?q={quote_plus(query)}"

        try:
            request = Request(
                url,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/124.0.0.0 Safari/537.36"
                    )
                },
            )
            with urlopen(request, timeout=6) as response:
                xml_bytes = response.read()
        except Exception:
            return []

        try:
            root = ET.fromstring(xml_bytes)
        except ET.ParseError:
            return []

        items: list[dict[str, str]] = []
        for item in root.findall(".//item")[:max_results]:
            title = unescape((item.findtext("title") or "").strip())
            link = (item.findtext("link") or "").strip()
            description = unescape((item.findtext("description") or "").strip())
            if not (title or link or description):
                continue
            items.append(
                {
                    "title": title,
                    "href": link,
                    "body": description,
                }
            )
        return items
