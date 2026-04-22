from __future__ import annotations

from pydantic import BaseModel


class VoiceChatResponse(BaseModel):
    session_id: str
    transcript: str
    response: str
    used_memory: bool
    used_internet: bool
    audio_path: str | None = None
