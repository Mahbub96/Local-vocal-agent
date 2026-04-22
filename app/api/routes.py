from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_async_db_session
from app.memory.long_term.retriever import LongTermMemoryRetriever
from app.schemas.chat import ChatRequest, ChatResponse
from app.schemas.memory import MemorySearchMatch, MemorySearchRequest, MemorySearchResponse
from app.schemas.voice import VoiceChatResponse
from app.services.chat_service import ChatService
from app.services.embedding_service import EmbeddingService
from app.services.memory_service import MemoryService
from app.services.voice_service import VoiceService


router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
    db_session: AsyncSession = Depends(get_async_db_session),
) -> ChatResponse:
    service = ChatService(db_session)
    return await service.handle_chat(
        message=payload.message,
        session_id=payload.session_id,
        user_id=payload.user_id,
        include_tts=payload.include_tts,
    )


@router.post("/voice-chat", response_model=VoiceChatResponse)
async def voice_chat(
    file: UploadFile = File(...),
    session_id: str | None = Form(default=None),
    user_id: str | None = Form(default=None),
    db_session: AsyncSession = Depends(get_async_db_session),
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


@router.post("/memory/search", response_model=MemorySearchResponse)
async def memory_search(
    payload: MemorySearchRequest,
    db_session: AsyncSession = Depends(get_async_db_session),
) -> MemorySearchResponse:
    memory_service = MemoryService(db_session)
    embedding_service = EmbeddingService()
    retriever = LongTermMemoryRetriever(
        embedding_service=embedding_service,
        memory_service=memory_service,
    )
    matches = await retriever.search(
        payload.query,
        top_k=payload.top_k,
        session_id=payload.session_id,
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
