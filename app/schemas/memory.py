from __future__ import annotations

from pydantic import BaseModel, Field


class MemorySearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    session_id: str | None = Field(default=None)
    top_k: int = Field(default=5, ge=1, le=20)


class MemorySearchMatch(BaseModel):
    message_id: str
    session_id: str
    role: str
    content: str
    score: float
    created_at: str | None = None


class MemorySearchResponse(BaseModel):
    matches: list[MemorySearchMatch]
