from __future__ import annotations

import asyncio
import contextlib
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import get_settings
from app.integrations.stt.whisper_stt import WhisperSTTService
from app.integrations.tts.tts_locale import prefers_bangla_tts
from app.schemas.voice import VoiceChatResponse
from app.services.chat_service import ChatService


settings = get_settings()


class VoiceService:
    """Handles end-to-end voice chat orchestration."""

    def __init__(self, db_session: AsyncSession) -> None:
        self.db_session = db_session
        self.chat_service = ChatService(db_session)
        self.stt_service = WhisperSTTService()

    async def handle_voice_chat(
        self,
        *,
        audio_bytes: bytes,
        filename: str,
        session_id: str | None = None,
        user_id: str | None = None,
    ) -> VoiceChatResponse:
        suffix = Path(filename).suffix or ".wav"
        input_path = settings.upload_dir / f"{uuid4().hex}{suffix}"
        input_path.write_bytes(audio_bytes)
        try:
            stt_lang: str | None = None
            if user_id:
                prof = await self.chat_service.memory_service.get_user_profile(user_id)
                raw = prof.get("language") if prof else None
                if isinstance(raw, str) and prefers_bangla_tts(raw):
                    stt_lang = "bn"
            try:
                transcript = await self.stt_service.transcribe(input_path, language=stt_lang)
            except asyncio.TimeoutError:
                raise HTTPException(
                    status_code=504,
                    detail="Speech recognition timed out. Try a shorter recording.",
                ) from None
            if not transcript:
                raise HTTPException(
                    status_code=422,
                    detail="Unable to extract text from audio. Please provide clearer speech.",
                )
            chat_result = await self.chat_service.handle_chat(
                message=transcript,
                session_id=session_id,
                user_id=user_id,
                include_tts=True,
                defer_tts=False,
            )
            return VoiceChatResponse(
                session_id=chat_result.session_id,
                transcript=transcript,
                response=chat_result.response,
                used_memory=chat_result.used_memory,
                used_internet=chat_result.used_internet,
                audio_path=chat_result.audio_path,
            )
        finally:
            with contextlib.suppress(OSError):
                input_path.unlink()
