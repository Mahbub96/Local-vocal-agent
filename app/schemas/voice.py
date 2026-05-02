from __future__ import annotations

from pydantic import BaseModel, Field


class VoiceChatResponse(BaseModel):
    session_id: str
    transcript: str
    response: str
    used_memory: bool
    used_internet: bool
    audio_path: str | None = None
    audio_url: str | None = Field(
        default=None,
        description="Path under API base for playback, e.g. tts/audio/uuid.wav",
    )
