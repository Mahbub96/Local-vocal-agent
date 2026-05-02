from __future__ import annotations

import asyncio
import logging
import threading
from pathlib import Path

from av.error import InvalidDataError
from faster_whisper import WhisperModel

from app.core.settings import get_settings


logger = logging.getLogger(__name__)


class STTInputError(Exception):
    """Raised when the audio file cannot be decoded for transcription."""


settings = get_settings()


class WhisperSTTService:
    """Async wrapper around a local Whisper model."""

    def __init__(self, model_size: str | None = None, device: str | None = None) -> None:
        self.model_size = model_size or settings.whisper_model_size
        self.device = device or settings.stt_device
        self._model: WhisperModel | None = None
        self._infer_lock = threading.Lock()

    def warm_load(self) -> None:
        """Load weights into RAM (startup); safe to call once."""
        with self._infer_lock:
            self._get_model()

    def _get_model(self) -> WhisperModel:
        if self._model is None:
            self._model = WhisperModel(
                self.model_size,
                device=self.device,
                compute_type=settings.stt_compute_type,
            )
        return self._model

    async def transcribe(self, audio_path: Path, *, language: str | None = None) -> str:
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(self._transcribe_sync, audio_path, language),
                timeout=settings.stt_transcribe_timeout_seconds,
            )
        except asyncio.TimeoutError:
            logger.error("STT timed out after %s s for %s", settings.stt_transcribe_timeout_seconds, audio_path.name)
            raise

    def _transcribe_sync(self, audio_path: Path, language: str | None) -> str:
        with self._infer_lock:
            model = self._get_model()
            kwargs: dict = {
                "beam_size": settings.stt_beam_size,
                "temperature": settings.stt_temperature,
                "vad_filter": settings.stt_vad_filter,
                "vad_parameters": {"min_silence_duration_ms": settings.stt_vad_min_silence_ms},
                "condition_on_previous_text": settings.stt_condition_on_previous_text,
            }
            if language:
                kwargs["language"] = language
            try:
                segments, _info = model.transcribe(str(audio_path), **kwargs)
            except InvalidDataError as exc:
                logger.warning("STT could not decode %s: %s", audio_path.name, exc)
                raise STTInputError("Audio could not be decoded.") from exc
            return " ".join(segment.text.strip() for segment in segments).strip()


_whisper_singleton: WhisperSTTService | None = None
_whisper_singleton_lock = threading.Lock()


def get_whisper_stt() -> WhisperSTTService:
    """Process-wide Whisper (one load); avoids reloading GB-scale weights per HTTP request."""
    global _whisper_singleton
    if _whisper_singleton is None:
        with _whisper_singleton_lock:
            if _whisper_singleton is None:
                _whisper_singleton = WhisperSTTService()
    return _whisper_singleton
