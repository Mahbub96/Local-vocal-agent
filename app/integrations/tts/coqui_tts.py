from __future__ import annotations

import asyncio
from pathlib import Path
from uuid import uuid4

from TTS.api import TTS

from app.core.settings import get_settings


settings = get_settings()


class CoquiTTSService:
    """Async wrapper for local Coqui TTS synthesis."""

    def __init__(self, model_name: str | None = None) -> None:
        self.model_name = model_name or settings.tts_model_name
        self._tts: TTS | None = None

    def _get_model(self) -> TTS:
        if self._tts is None:
            self._tts = TTS(model_name=self.model_name, progress_bar=False)
        return self._tts

    def build_output_path(self, *, file_stem: str | None = None) -> Path:
        return settings.tts_output_dir / f"{file_stem or uuid4().hex}.wav"

    async def synthesize_to_file(self, text: str, *, file_stem: str | None = None) -> Path:
        output_path = self.build_output_path(file_stem=file_stem)
        await asyncio.to_thread(self._synthesize_sync, text, output_path)
        return output_path

    def _synthesize_sync(self, text: str, output_path: Path) -> None:
        model = self._get_model()
        model.tts_to_file(text=text, file_path=str(output_path))
