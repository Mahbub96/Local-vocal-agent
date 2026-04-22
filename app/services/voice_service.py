from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import get_settings
from app.integrations.stt.whisper_stt import WhisperSTTService
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

        transcript = await self.stt_service.transcribe(input_path)
        chat_result = await self.chat_service.handle_chat(
            message=transcript,
            session_id=session_id,
            user_id=user_id,
            include_tts=True,
            defer_tts=True,
        )
        return VoiceChatResponse(
            session_id=chat_result.session_id,
            transcript=transcript,
            response=chat_result.response,
            used_memory=chat_result.used_memory,
            used_internet=chat_result.used_internet,
            audio_path=chat_result.audio_path,
        )
