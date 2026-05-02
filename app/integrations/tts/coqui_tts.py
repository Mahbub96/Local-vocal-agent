from __future__ import annotations

import asyncio
import logging
import threading
from pathlib import Path
from uuid import uuid4

from TTS.api import TTS

from app.core.settings import get_settings
from app.integrations.tts.tts_text import prepare_tts_text

logger = logging.getLogger(__name__)
settings = get_settings()

# Serialize Coqui GPU/CPU work — concurrent calls can OOM or corrupt output.
_tts_model_lock = threading.Lock()


class CoquiTTSService:
    """Async wrapper for local Coqui TTS synthesis (defensive: timeout, sanitize, lock)."""

    def __init__(self, model_name: str | None = None) -> None:
        self.model_name = model_name or settings.tts_model_name
        self._tts: TTS | None = None

    def _get_model(self) -> TTS:
        if self._tts is None:
            self._tts = TTS(model_name=self.model_name, progress_bar=False)
        return self._tts

    def build_output_path(self, *, file_stem: str | None = None) -> Path:
        return settings.tts_output_dir / f"{file_stem or uuid4().hex}.wav"

    @staticmethod
    def _unlink_quiet(path: Path) -> None:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass

    async def synthesize_to_file(self, text: str, *, file_stem: str | None = None) -> Path | None:
        """
        Write assistant speech to WAV under `tts_output_dir`.
        Returns ``None`` on empty input, timeout, or synthesis failure (chat still succeeds).
        """
        prepared = prepare_tts_text(text, settings.tts_max_chars)
        if not prepared:
            logger.warning("TTS skipped: empty or invalid text after preparation")
            return None

        output_path = self.build_output_path(file_stem=file_stem)
        self._unlink_quiet(output_path)

        try:
            await asyncio.wait_for(
                asyncio.to_thread(self._synthesize_sync, prepared, output_path),
                timeout=settings.tts_timeout_seconds,
            )
        except asyncio.TimeoutError:
            logger.error("TTS timed out after %s s (output=%s)", settings.tts_timeout_seconds, output_path.name)
            self._unlink_quiet(output_path)
            return None
        except Exception:
            logger.exception("TTS synthesis raised (output=%s)", output_path.name)
            self._unlink_quiet(output_path)
            return None

        try:
            if not output_path.is_file():
                logger.error("TTS missing output file: %s", output_path)
                return None
            size = output_path.stat().st_size
            if size < settings.tts_min_output_bytes:
                logger.error("TTS output too small (%s bytes), removing: %s", size, output_path)
                self._unlink_quiet(output_path)
                return None
        except OSError as exc:
            logger.error("TTS cannot stat output: %s — %s", output_path, exc)
            self._unlink_quiet(output_path)
            return None

        return output_path

    def _synthesize_sync(self, text: str, output_path: Path) -> None:
        with _tts_model_lock:
            model = self._get_model()
            model.tts_to_file(text=text, file_path=str(output_path))
