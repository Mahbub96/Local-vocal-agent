from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_async_db_session
from app.memory.long_term.retriever import LongTermMemoryRetriever
from app.schemas.chat import ChatRequest, ChatResponse
from app.schemas.memory import MemorySearchMatch, MemorySearchResponse
from app.schemas.voice import VoiceChatResponse
from app.services.chat_service import ChatService
from app.services.embedding_service import EmbeddingService
from app.services.memory_service import MemoryService
from app.services.voice_service import VoiceService


router = APIRouter()


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
    return await service.handle_voice_chat(
        audio_bytes=audio_bytes,
        filename=file.filename or "input.wav",
        session_id=session_id,
        user_id=user_id,
    )


@router.get("/memory/search")
async def memory_search(
    query: Annotated[str, Query(min_length=1)],
    db_session: Annotated[AsyncSession, Depends(get_async_db_session)],
    top_k: Annotated[int, Query(ge=1, le=20)] = 5,
    session_id: Annotated[str | None, Query()] = None,
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
