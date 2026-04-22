from __future__ import annotations

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="User message.")
    session_id: str | None = Field(default=None, description="Existing conversation session id.")
    user_id: str | None = Field(default=None, description="Optional user identifier.")
    include_tts: bool = Field(default=False, description="Generate audio output in addition to text.")


class ChatResponse(BaseModel):
    session_id: str
    user_message_id: str
    assistant_message_id: str
    response: str
    used_memory: bool
    used_internet: bool
    audio_path: str | None = None
