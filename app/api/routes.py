from __future__ import annotations

import asyncio
import json
from pathlib import Path
import subprocess
import time
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
import psutil
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_async_db_session
from app.core.settings import get_settings
from app.memory.long_term.retriever import LongTermMemoryRetriever
from app.schemas.chat import ChatRequest, ChatResponse
from app.schemas.memory import MemorySearchMatch, MemorySearchResponse
from app.schemas.ui import (
    CapabilitiesResponse,
    ConversationMessage,
    FileContentResponse,
    FileEntry,
    FileListResponse,
    FileSearchMatch,
    FileSearchResponse,
    MessageFeedbackRequest,
    MessageFeedbackResponse,
    MemorySummaryResponse,
    SessionListItem,
    SessionMessagesResponse,
    SessionUpdateRequest,
    SessionsResponse,
    SystemMetricsResponse,
    SystemOverviewResponse,
    SystemStatusResponse,
    ThinkingProcessResponse,
    ThinkingStep,
    ToolActivityItem,
    ToolActivityResponse,
    UsageSummaryResponse,
    MeResponse,
    UserProfile,
    UserProfileResponse,
    VoiceStatusResponse,
)
from app.schemas.voice import VoiceChatResponse
from app.agents.assistant_agent import ModelUnavailableError
from app.services.chat_service import ChatService
from app.services.embedding_service import EmbeddingService
from app.services.memory_service import MemoryService
from app.services.voice_status_service import voice_status_service
from app.services.voice_service import VoiceService


router = APIRouter()
settings = get_settings()
APP_START_TIME = time.time()
SESSION_NOT_FOUND_DETAIL = "Session not found."
MAX_FILE_READ_BYTES = 1_000_000
MAX_FILE_SEARCH_BYTES = 500_000


async def _compose_thinking_process(
    session_id: str,
    memory_service: MemoryService,
) -> ThinkingProcessResponse:
    session = await memory_service.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=SESSION_NOT_FOUND_DETAIL)

    messages = await memory_service.fetch_session_messages(session_id, limit=20)
    latest_user = next((msg for msg in reversed(messages) if msg.role == "user"), None)
    latest_assistant = next((msg for msg in reversed(messages) if msg.role == "assistant"), None)
    if latest_user is None:
        return ThinkingProcessResponse(session_id=session_id, steps=[])

    used_internet = (
        latest_assistant is not None and latest_assistant.tool_name == "internet_search_tool"
    )
    steps = [
        ThinkingStep(
            key="understanding",
            label="Understanding your question",
            status="completed",
            detail=(latest_user.content[:120] + "...")
            if len(latest_user.content) > 120
            else latest_user.content,
        ),
        ThinkingStep(
            key="searching",
            label="Searching the internet",
            status="completed" if used_internet else "skipped",
            detail="Enabled for realtime query." if used_internet else "Not required for this query.",
        ),
        ThinkingStep(
            key="retrieving",
            label="Retrieving relevant information",
            status="completed",
            detail="Pulled recent + semantic memory context.",
        ),
        ThinkingStep(
            key="preferences",
            label="Checking your preferences",
            status="completed",
            detail=f"Session user: {session.user_id or 'anonymous'}",
        ),
        ThinkingStep(
            key="response",
            label="Generating response",
            status="completed" if latest_assistant else "in_progress",
            detail="Assistant response generated." if latest_assistant else "Assistant response pending.",
        ),
    ]
    return ThinkingProcessResponse(session_id=session_id, steps=steps)


@router.post("/chat", responses={422: {"description": "Validation or business-rule error."}})
async def chat(
    payload: ChatRequest,
    db_session: Annotated[AsyncSession, Depends(get_async_db_session)],
) -> ChatResponse:
    service = ChatService(db_session)
    try:
        return await service.handle_chat(
            message=payload.message,
            session_id=payload.session_id,
            user_id=payload.user_id,
            include_tts=payload.include_tts,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ModelUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post(
    "/voice-chat",
    responses={
        400: {"description": "Uploaded audio file is empty."},
        422: {"description": "Unable to extract text from audio."},
    },
)
async def voice_chat(
    file: Annotated[UploadFile, File(...)],
    db_session: Annotated[AsyncSession, Depends(get_async_db_session)],
    session_id: Annotated[str | None, Form()] = None,
    user_id: Annotated[str | None, Form()] = None,
) -> VoiceChatResponse:
    audio_bytes = await file.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Uploaded audio file is empty.")

    service = VoiceService(db_session)
    await voice_status_service.set_state("listening", detail="Audio received", audio_level=45.0)
    try:
        await voice_status_service.set_state("transcribing", detail="Converting speech to text")
        result = await service.handle_voice_chat(
            audio_bytes=audio_bytes,
            filename=file.filename or "input.wav",
            session_id=session_id,
            user_id=user_id,
        )
        await voice_status_service.set_state(
            "speaking",
            detail="Voice response ready",
            audio_level=58.0,
        )
        return result
    finally:
        # Keep "speaking" state briefly for UI transition.
        await asyncio.sleep(0.2)
        await voice_status_service.set_state("idle", detail="Waiting for input")


@router.get("/memory/search")
async def memory_search(
    query: Annotated[str, Query(min_length=1)],
    db_session: Annotated[AsyncSession, Depends(get_async_db_session)],
    top_k: Annotated[int, Query(ge=1, le=20)] = 5,
    session_id: Annotated[str | None, Query()] = None,
    user_id: Annotated[str | None, Query()] = None,
) -> MemorySearchResponse:
    memory_service = MemoryService(db_session)
    embedding_service = EmbeddingService()
    retriever = LongTermMemoryRetriever(
        embedding_service=embedding_service,
        memory_service=memory_service,
    )
    matches = await retriever.search(
        query,
        top_k=top_k,
        session_id=session_id,
        user_id=user_id,
    )
    return MemorySearchResponse(
        matches=[
            MemorySearchMatch(
                message_id=match.message.id,
                session_id=match.message.session_id,
                role=match.message.role,
                content=match.message.content,
                score=match.score,
                created_at=match.message.created_at.isoformat()
                if match.message.created_at
                else None,
            )
            for match in matches
        ]
    )


@router.get("/sessions")
async def list_sessions(
    db_session: Annotated[AsyncSession, Depends(get_async_db_session)],
    user_id: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    is_active: Annotated[int, Query(ge=0, le=1)] = 1,
) -> SessionsResponse:
    memory_service = MemoryService(db_session)
    sessions = await memory_service.list_sessions(user_id=user_id, limit=limit, is_active=is_active)
    payload: list[SessionListItem] = []
    for session in sessions:
        message_count = await memory_service.count_session_messages(session.id)
        payload.append(
            SessionListItem(
                session_id=session.id,
                user_id=session.user_id,
                title=session.title,
                message_count=message_count,
                last_message_at=session.last_message_at.isoformat()
                if session.last_message_at
                else None,
                created_at=session.created_at.isoformat() if session.created_at else None,
            )
        )
    return SessionsResponse(sessions=payload)


@router.patch("/sessions/{session_id}")
async def update_session(
    session_id: str,
    payload: SessionUpdateRequest,
    db_session: Annotated[AsyncSession, Depends(get_async_db_session)],
) -> SessionListItem:
    memory_service = MemoryService(db_session)
    if payload.title is None and payload.is_active is None:
        raise HTTPException(status_code=422, detail="At least one update field is required.")

    session = await memory_service.update_session(
        session_id,
        title=payload.title,
        is_active=payload.is_active,
    )
    if session is None:
        raise HTTPException(status_code=404, detail=SESSION_NOT_FOUND_DETAIL)

    message_count = await memory_service.count_session_messages(session.id)
    return SessionListItem(
        session_id=session.id,
        user_id=session.user_id,
        title=session.title,
        message_count=message_count,
        last_message_at=session.last_message_at.isoformat() if session.last_message_at else None,
        created_at=session.created_at.isoformat() if session.created_at else None,
    )


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str,
    db_session: Annotated[AsyncSession, Depends(get_async_db_session)],
) -> dict[str, str]:
    memory_service = MemoryService(db_session)
    session = await memory_service.archive_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=SESSION_NOT_FOUND_DETAIL)
    return {"status": "archived", "session_id": session_id}


@router.post("/sessions/{session_id}/restore")
async def restore_session(
    session_id: str,
    db_session: Annotated[AsyncSession, Depends(get_async_db_session)],
) -> dict[str, str]:
    memory_service = MemoryService(db_session)
    session = await memory_service.restore_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=SESSION_NOT_FOUND_DETAIL)
    return {"status": "restored", "session_id": session_id}


@router.delete("/sessions/{session_id}/permanent")
async def delete_session_permanently(
    session_id: str,
    db_session: Annotated[AsyncSession, Depends(get_async_db_session)],
) -> dict[str, str]:
    memory_service = MemoryService(db_session)
    deleted = await memory_service.delete_session_permanently(session_id)
    if deleted is None:
        raise HTTPException(status_code=404, detail=SESSION_NOT_FOUND_DETAIL)
    if deleted is False:
        raise HTTPException(
            status_code=409,
            detail="Session must be archived before permanent deletion.",
        )
    return {"status": "deleted", "session_id": session_id}


@router.get("/sessions/{session_id}/messages")
async def get_session_messages(
    session_id: str,
    db_session: Annotated[AsyncSession, Depends(get_async_db_session)],
    limit: Annotated[int, Query(ge=1, le=500)] = 200,
) -> SessionMessagesResponse:
    memory_service = MemoryService(db_session)
    session = await memory_service.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=SESSION_NOT_FOUND_DETAIL)

    messages = await memory_service.fetch_session_messages(session_id, limit=limit)
    return SessionMessagesResponse(
        session_id=session_id,
        messages=[
            ConversationMessage(
                id=message.id,
                role=message.role,
                content=message.content,
                sequence_number=message.sequence_number,
                created_at=message.created_at.isoformat() if message.created_at else None,
                tool_name=message.tool_name,
                token_count=message.token_count,
            )
            for message in messages
        ],
    )


@router.get("/sessions/{session_id}/memory-summary")
async def get_memory_summary(
    session_id: str,
    db_session: Annotated[AsyncSession, Depends(get_async_db_session)],
) -> MemorySummaryResponse:
    memory_service = MemoryService(db_session)
    session = await memory_service.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=SESSION_NOT_FOUND_DETAIL)

    messages = await memory_service.fetch_session_messages(session_id)
    user_count = sum(1 for message in messages if message.role == "user")
    assistant_count = sum(1 for message in messages if message.role == "assistant")
    return MemorySummaryResponse(
        session_id=session_id,
        recent_user_messages=user_count,
        recent_assistant_messages=assistant_count,
        total_messages=len(messages),
    )


@router.get("/sessions/{session_id}/thinking-process")
async def get_thinking_process(
    session_id: str,
    db_session: Annotated[AsyncSession, Depends(get_async_db_session)],
) -> ThinkingProcessResponse:
    memory_service = MemoryService(db_session)
    return await _compose_thinking_process(session_id, memory_service)


@router.get("/sessions/{session_id}/thinking-stream")
async def stream_thinking_process(
    session_id: str,
    db_session: Annotated[AsyncSession, Depends(get_async_db_session)],
    interval_ms: Annotated[int, Query(ge=200, le=5000)] = 1000,
    max_events: Annotated[int, Query(ge=1, le=120)] = 20,
) -> StreamingResponse:
    memory_service = MemoryService(db_session)

    # Fail fast on invalid session before opening stream.
    _ = await memory_service.get_session(session_id)
    if _ is None:
        raise HTTPException(status_code=404, detail=SESSION_NOT_FOUND_DETAIL)

    async def event_generator():
        for _idx in range(max_events):
            snapshot = await _compose_thinking_process(session_id, memory_service)
            data = json.dumps(snapshot.model_dump(), ensure_ascii=True)
            yield f"event: thinking_update\ndata: {data}\n\n"
            await asyncio.sleep(interval_ms / 1000)
        yield "event: stream_complete\ndata: {\"status\":\"done\"}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


def _read_gpu_percent_macos() -> float | None:
    """
    Best-effort GPU utilization read on macOS.
    Returns None if metric is unavailable.
    """
    try:
        result = subprocess.run(
            ["powermetrics", "-n", "1", "-s", "gpu_power", "-i", "1000"],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None

    if result.returncode != 0:
        return None

    for line in result.stdout.splitlines():
        lower = line.lower()
        if "gpu active residency" in lower and "%" in line:
            try:
                value = float(line.split(":", 1)[1].split("%", 1)[0].strip())
                return max(0.0, min(100.0, value))
            except (IndexError, ValueError):
                return None
    return None


def _resolve_files_path(relative_path: str | None) -> Path:
    root = settings.files_root.resolve()
    candidate = (root / (relative_path or "")).resolve()
    if root != candidate and root not in candidate.parents:
        raise HTTPException(status_code=400, detail="Path escapes configured files root.")
    return candidate


def _search_matches_in_file(
    file_path: Path,
    *,
    query: str,
    root: Path,
    max_line_chars: int = 500,
) -> list[FileSearchMatch]:
    if not file_path.is_file() or file_path.stat().st_size > MAX_FILE_SEARCH_BYTES:
        return []
    try:
        lines = file_path.read_text(encoding="utf-8").splitlines()
    except UnicodeDecodeError:
        return []

    lowered_query = query.lower()
    matches: list[FileSearchMatch] = []
    for idx, line in enumerate(lines, start=1):
        if lowered_query in line.lower():
            matches.append(
                FileSearchMatch(
                    path=str(file_path.relative_to(root)),
                    line_number=idx,
                    line=line[:max_line_chars],
                )
            )
    return matches


def _build_system_metrics() -> SystemMetricsResponse:
    cpu_percent = float(psutil.cpu_percent(interval=0.2))
    memory_percent = float(psutil.virtual_memory().percent)
    gpu_percent = _read_gpu_percent_macos()
    npu_percent = None
    return SystemMetricsResponse(
        cpu_percent=max(0.0, min(100.0, cpu_percent)),
        memory_percent=max(0.0, min(100.0, memory_percent)),
        gpu_percent=gpu_percent,
        npu_percent=npu_percent,
    )


def _build_system_status() -> SystemStatusResponse:
    try:
        load_1m, load_5m, load_15m = (float(x) for x in __import__("os").getloadavg())
    except (AttributeError, OSError):
        load_1m, load_5m, load_15m = (None, None, None)

    return SystemStatusResponse(
        app_name=settings.app_name,
        app_env=settings.app_env,
        uptime_seconds=int(time.time() - APP_START_TIME),
        model_name=settings.ollama_model,
        load_avg_1m=load_1m,
        load_avg_5m=load_5m,
        load_avg_15m=load_15m,
        sqlite_path=str(settings.sqlite_path),
        chroma_path=str(settings.chroma_path),
    )


@router.get("/system/metrics")
async def get_system_metrics() -> SystemMetricsResponse:
    return _build_system_metrics()


@router.get("/system/overview")
async def get_system_overview() -> SystemOverviewResponse:
    return SystemOverviewResponse(
        metrics=_build_system_metrics(),
        status=_build_system_status(),
    )


@router.get("/tools/activity")
async def get_tool_activity(
    db_session: Annotated[AsyncSession, Depends(get_async_db_session)],
    session_id: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ToolActivityResponse:
    memory_service = MemoryService(db_session)
    activities = await memory_service.fetch_tool_activity(session_id=session_id, limit=limit)
    return ToolActivityResponse(
        activities=[
            ToolActivityItem(
                session_id=message.session_id,
                message_id=message.id,
                tool_name=str(message.tool_name),
                created_at=message.created_at.isoformat() if message.created_at else None,
                role=message.role,
            )
            for message in activities
        ]
    )


@router.get("/system/status")
async def get_system_status() -> SystemStatusResponse:
    return _build_system_status()


@router.get("/usage/summary")
async def get_usage_summary(
    user_id: Annotated[str, Query(min_length=1)],
    db_session: Annotated[AsyncSession, Depends(get_async_db_session)],
) -> UsageSummaryResponse:
    memory_service = MemoryService(db_session)
    usage = await memory_service.get_usage_summary(user_id)
    return UsageSummaryResponse(user_id=user_id, **usage)


@router.get("/profile")
async def get_user_profile(
    user_id: Annotated[str, Query(min_length=1)],
    db_session: Annotated[AsyncSession, Depends(get_async_db_session)],
) -> UserProfileResponse:
    memory_service = MemoryService(db_session)
    profile_data = await memory_service.get_user_profile(user_id)
    return UserProfileResponse(user_id=user_id, profile=UserProfile(**profile_data))


@router.put("/profile")
async def update_user_profile(
    user_id: Annotated[str, Query(min_length=1)],
    payload: UserProfile,
    db_session: Annotated[AsyncSession, Depends(get_async_db_session)],
) -> UserProfileResponse:
    memory_service = MemoryService(db_session)
    updated_profile = await memory_service.upsert_user_profile(
        user_id,
        payload.model_dump(),
    )
    return UserProfileResponse(user_id=user_id, profile=UserProfile(**updated_profile))


@router.get("/me")
async def get_me(
    user_id: Annotated[str, Query(min_length=1)],
    db_session: Annotated[AsyncSession, Depends(get_async_db_session)],
) -> MeResponse:
    memory_service = MemoryService(db_session)
    profile_data = await memory_service.get_user_profile(user_id)
    profile = UserProfile(**profile_data)
    return MeResponse(
        user_id=user_id,
        display_name=profile.name,
        language=profile.language,
        location=profile.location,
        profession=profile.profession,
    )


@router.put("/me")
async def update_me(
    user_id: Annotated[str, Query(min_length=1)],
    payload: UserProfile,
    db_session: Annotated[AsyncSession, Depends(get_async_db_session)],
) -> MeResponse:
    memory_service = MemoryService(db_session)
    updated_profile = await memory_service.upsert_user_profile(
        user_id,
        payload.model_dump(),
    )
    profile = UserProfile(**updated_profile)
    return MeResponse(
        user_id=user_id,
        display_name=profile.name,
        language=profile.language,
        location=profile.location,
        profession=profile.profession,
    )


@router.get("/capabilities")
async def get_capabilities() -> CapabilitiesResponse:
    return CapabilitiesResponse(
        chat=True,
        voice_chat=True,
        memory_search=True,
        sessions=True,
        session_restore=True,
        session_permanent_delete=True,
        thinking_process=True,
        thinking_stream=True,
        files=True,
        tools_activity=True,
        system_status=True,
        system_metrics=True,
        system_overview=True,
        profile=True,
        me=True,
        message_feedback=True,
    )


@router.post("/messages/{message_id}/feedback")
async def set_message_feedback(
    message_id: str,
    payload: MessageFeedbackRequest,
    db_session: Annotated[AsyncSession, Depends(get_async_db_session)],
) -> MessageFeedbackResponse:
    memory_service = MemoryService(db_session)
    value = await memory_service.set_message_feedback(message_id, payload.value)
    if value is None:
        raise HTTPException(status_code=404, detail="Message not found.")
    return MessageFeedbackResponse(message_id=message_id, value=value)


@router.get("/messages/{message_id}/feedback")
async def get_message_feedback(
    message_id: str,
    db_session: Annotated[AsyncSession, Depends(get_async_db_session)],
) -> MessageFeedbackResponse:
    memory_service = MemoryService(db_session)
    value = await memory_service.get_message_feedback(message_id)
    if value is None:
        value = "none"
    return MessageFeedbackResponse(message_id=message_id, value=value)


@router.get("/voice/status")
async def get_voice_status() -> VoiceStatusResponse:
    snapshot = await voice_status_service.get_snapshot()
    return VoiceStatusResponse(**snapshot)


@router.get("/voice/status-stream")
async def stream_voice_status(
    interval_ms: Annotated[int, Query(ge=200, le=5000)] = 700,
    max_events: Annotated[int, Query(ge=1, le=120)] = 30,
) -> StreamingResponse:
    async def event_generator():
        for _ in range(max_events):
            snapshot = await voice_status_service.get_snapshot()
            data = json.dumps(snapshot, ensure_ascii=True)
            yield f"event: voice_status\ndata: {data}\n\n"
            await asyncio.sleep(interval_ms / 1000)
        yield "event: stream_complete\ndata: {\"status\":\"done\"}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/files")
async def list_files(
    path: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 200,
) -> FileListResponse:
    directory = _resolve_files_path(path)
    if not directory.exists():
        raise HTTPException(status_code=404, detail="Path not found.")
    if not directory.is_dir():
        raise HTTPException(status_code=400, detail="Path is not a directory.")

    root = settings.files_root.resolve()
    entries: list[FileEntry] = []
    for item in sorted(directory.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))[:limit]:
        stat = item.stat()
        entries.append(
            FileEntry(
                name=item.name,
                path=str(item.relative_to(root)),
                is_dir=item.is_dir(),
                size=None if item.is_dir() else int(stat.st_size),
                modified_at=time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(stat.st_mtime)),
            )
        )

    rel_current = str(directory.relative_to(root))
    return FileListResponse(
        root=str(root),
        current_path="" if rel_current == "." else rel_current,
        entries=entries,
    )


@router.get("/files/content")
async def get_file_content(
    path: Annotated[str, Query(min_length=1)],
) -> FileContentResponse:
    file_path = _resolve_files_path(path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found.")
    if not file_path.is_file():
        raise HTTPException(status_code=400, detail="Path is not a file.")
    if file_path.stat().st_size > MAX_FILE_READ_BYTES:
        raise HTTPException(status_code=413, detail="File too large to read via API.")

    try:
        content = file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=415, detail="File is not UTF-8 text.") from None
    return FileContentResponse(path=path, content=content)


@router.get("/files/search")
async def search_files(
    query: Annotated[str, Query(min_length=1)],
    path: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> FileSearchResponse:
    scope = _resolve_files_path(path)
    if not scope.exists():
        raise HTTPException(status_code=404, detail="Path not found.")

    root = settings.files_root.resolve()
    search_space = [scope] if scope.is_file() else list(scope.rglob("*"))
    matches: list[FileSearchMatch] = []
    for item in search_space:
        if len(matches) >= limit:
            break
        file_matches = _search_matches_in_file(item, query=query, root=root)
        if not file_matches:
            continue
        remaining = limit - len(matches)
        matches.extend(file_matches[:remaining])
    return FileSearchResponse(query=query, matches=matches)
