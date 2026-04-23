from __future__ import annotations

from pydantic import BaseModel, Field


class SessionListItem(BaseModel):
    session_id: str
    user_id: str | None = None
    title: str | None = None
    message_count: int
    last_message_at: str | None = None
    created_at: str | None = None


class SessionsResponse(BaseModel):
    sessions: list[SessionListItem]


class SessionUpdateRequest(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    is_active: int | None = Field(default=None, ge=0, le=1)


class ConversationMessage(BaseModel):
    id: str
    role: str
    content: str
    sequence_number: int
    created_at: str | None = None
    tool_name: str | None = None
    token_count: int | None = None


class SessionMessagesResponse(BaseModel):
    session_id: str
    messages: list[ConversationMessage]


class ToolActivityItem(BaseModel):
    session_id: str
    message_id: str
    tool_name: str
    created_at: str | None = None
    role: str


class ToolActivityResponse(BaseModel):
    activities: list[ToolActivityItem]


class MemorySummaryResponse(BaseModel):
    session_id: str
    recent_user_messages: int
    recent_assistant_messages: int
    total_messages: int


class SystemStatusResponse(BaseModel):
    app_name: str
    app_env: str
    uptime_seconds: int
    model_name: str | None = None
    load_avg_1m: float | None = None
    load_avg_5m: float | None = None
    load_avg_15m: float | None = None
    sqlite_path: str
    chroma_path: str


class UsageSummaryResponse(BaseModel):
    user_id: str
    total_messages: int
    assistant_messages: int
    total_tokens: int


class UserProfile(BaseModel):
    name: str | None = None
    language: str | None = None
    location: str | None = None
    profession: str | None = None
    project: str | None = None
    preferences: list[str] = []


class UserProfileResponse(BaseModel):
    user_id: str
    profile: UserProfile


class ThinkingStep(BaseModel):
    key: str
    label: str
    status: str
    detail: str | None = None


class ThinkingProcessResponse(BaseModel):
    session_id: str
    steps: list[ThinkingStep]


class SystemMetricsResponse(BaseModel):
    cpu_percent: float
    memory_percent: float
    gpu_percent: float | None = None
    npu_percent: float | None = None


class SystemOverviewResponse(BaseModel):
    """Single round-trip for dashboard: metrics + status."""

    metrics: SystemMetricsResponse
    status: SystemStatusResponse


class FileEntry(BaseModel):
    name: str
    path: str
    is_dir: bool
    size: int | None = None
    modified_at: str | None = None


class FileListResponse(BaseModel):
    root: str
    current_path: str
    entries: list[FileEntry]


class FileContentResponse(BaseModel):
    path: str
    content: str


class FileSearchMatch(BaseModel):
    path: str
    line_number: int
    line: str


class FileSearchResponse(BaseModel):
    query: str
    matches: list[FileSearchMatch]


class MessageFeedbackRequest(BaseModel):
    value: str = Field(..., pattern="^(like|dislike|none)$")


class MessageFeedbackResponse(BaseModel):
    message_id: str
    value: str


class VoiceStatusResponse(BaseModel):
    state: str
    audio_level: float
    detail: str | None = None
    updated_at: float


class MeResponse(BaseModel):
    user_id: str
    display_name: str | None = None
    language: str | None = None
    location: str | None = None
    profession: str | None = None


class CapabilitiesResponse(BaseModel):
    chat: bool
    voice_chat: bool
    memory_search: bool
    sessions: bool
    session_restore: bool
    session_permanent_delete: bool
    thinking_process: bool
    thinking_stream: bool
    files: bool
    tools_activity: bool
    system_status: bool
    system_metrics: bool
    system_overview: bool
    profile: bool
    me: bool
    message_feedback: bool
