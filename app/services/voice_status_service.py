from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field


@dataclass(slots=True)
class VoiceStatusState:
    state: str = "idle"
    audio_level: float = 0.0
    detail: str | None = None
    updated_at: float = field(default_factory=time.time)


class VoiceStatusService:
    def __init__(self) -> None:
        self._state = VoiceStatusState()
        self._lock = asyncio.Lock()

    async def set_state(self, state: str, *, detail: str | None = None, audio_level: float = 0.0) -> None:
        async with self._lock:
            self._state = VoiceStatusState(
                state=state,
                detail=detail,
                audio_level=max(0.0, min(100.0, float(audio_level))),
                updated_at=time.time(),
            )

    async def get_snapshot(self) -> dict[str, object]:
        async with self._lock:
            return {
                "state": self._state.state,
                "audio_level": self._state.audio_level,
                "detail": self._state.detail,
                "updated_at": self._state.updated_at,
            }


voice_status_service = VoiceStatusService()
