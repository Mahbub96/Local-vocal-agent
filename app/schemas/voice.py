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
    skipped: bool = Field(
        default=False,
        description="True when voice was ignored (wake gate); no messages stored.",
    )
    skip_reason: str | None = Field(
        default=None,
        description="wake_gate | no_speech — why nothing was added to chat.",
    )
    voice_listen_paused: bool | None = Field(
        default=None,
        description="Echo of profile flag after this call (for UI).",
    )
    voice_wake_session_active: bool | None = Field(
        default=None,
        description="True after wake in quiet mode until stop — follow-up utterances need no wake word.",
    )
