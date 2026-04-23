from __future__ import annotations

import asyncio
from pathlib import Path

from faster_whisper import WhisperModel

from app.core.settings import get_settings


settings = get_settings()


class WhisperSTTService:
    """Async wrapper around a local Whisper model."""

    def __init__(self, model_size: str | None = None, device: str | None = None) -> None:
        self.model_size = model_size or settings.whisper_model_size
        self.device = device or settings.stt_device
        self._model: WhisperModel | None = None

    def _get_model(self) -> WhisperModel:
        if self._model is None:
            self._model = WhisperModel(self.model_size, device=self.device)
        return self._model

    async def transcribe(self, audio_path: Path) -> str:
        return await asyncio.to_thread(self._transcribe_sync, audio_path)

    def _transcribe_sync(self, audio_path: Path) -> str:
        model = self._get_model()
        segments, _info = model.transcribe(
            str(audio_path),
            beam_size=settings.stt_beam_size,
            temperature=settings.stt_temperature,
            vad_filter=settings.stt_vad_filter,
            vad_parameters={"min_silence_duration_ms": settings.stt_vad_min_silence_ms},
        )
        return " ".join(segment.text.strip() for segment in segments).strip()
