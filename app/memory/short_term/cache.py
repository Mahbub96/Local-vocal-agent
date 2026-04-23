from __future__ import annotations

from collections import defaultdict, deque
from collections.abc import Iterable

from app.core.settings import get_settings


settings = get_settings()


class ShortTermMemoryStore:
    """In-process cache of the most recent messages for each session."""

    def __init__(self, limit: int | None = None) -> None:
        self.limit = limit or settings.short_term_message_limit
        self._cache: dict[str, deque[dict[str, str]]] = defaultdict(
            lambda: deque(maxlen=self.limit)
        )

    def append(self, session_id: str, role: str, content: str) -> None:
        self._cache[session_id].append({"role": role, "content": content})

    def extend(self, session_id: str, messages: Iterable[dict[str, str]]) -> None:
        for message in messages:
            self._cache[session_id].append(message)

    def get(self, session_id: str) -> list[dict[str, str]]:
        cached = self._cache.get(session_id)
        return list(cached) if cached is not None else []

    def clear(self, session_id: str) -> None:
        self._cache.pop(session_id, None)


short_term_memory_store = ShortTermMemoryStore()
