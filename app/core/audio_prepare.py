"""Normalize uploaded audio to PCM WAV before faster-whisper (PyAV) decode."""

from __future__ import annotations

import contextlib
import logging
import shutil
import subprocess
from pathlib import Path
from uuid import uuid4

from app.core.settings import get_settings

logger = logging.getLogger(__name__)

# Browser/MediaRecorder containers; PyAV often fails on these without ffmpeg.
_FFMPEG_EXTENSIONS = frozenset(
    {".webm", ".ogg", ".oga", ".mp4", ".m4a", ".mp3", ".opus", ".flac", ".aac", ".mkv"}
)


class FFmpegUnavailableError(Exception):
    """ffmpeg is required for this container/codec but was not found on PATH."""


class AudioNormalizeError(Exception):
    """ffmpeg could not produce valid WAV from the source."""


def prepare_for_whisper(
    source: Path,
    *,
    output_dir: Path,
    timeout_seconds: float | None = None,
) -> tuple[Path, list[Path]]:
    """Return (path for Whisper, extra files to delete after STT).

    When no conversion runs, returns ``(source, [])``.
    """
    if timeout_seconds is None:
        timeout_seconds = float(get_settings().audio_ffmpeg_timeout_seconds)

    ext = source.suffix.lower()
    if ext == ".wav" or ext not in _FFMPEG_EXTENSIONS:
        return source, []

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise FFmpegUnavailableError(
            "This audio format (e.g. WebM) requires ffmpeg. Install ffmpeg and ensure it is on PATH."
        )

    out = output_dir / f"{uuid4().hex}.wav"
    cmd = [
        ffmpeg,
        "-nostdin",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(source),
        "-ac",
        "1",
        "-ar",
        "16000",
        "-c:a",
        "pcm_s16le",
        str(out),
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=timeout_seconds)
    except subprocess.TimeoutExpired as exc:
        with contextlib.suppress(OSError):
            out.unlink(missing_ok=True)
        logger.warning("ffmpeg normalize timed out for %s", source.name)
        raise AudioNormalizeError("Audio conversion timed out. Try a shorter recording.") from exc
    except subprocess.CalledProcessError as exc:
        with contextlib.suppress(OSError):
            out.unlink(missing_ok=True)
        err = (exc.stderr or b"").decode(errors="replace").strip()
        logger.warning("ffmpeg failed for %s: %s", source.name, err)
        raise AudioNormalizeError(
            "Could not decode audio. The recording may be incomplete; try again."
        ) from exc

    if not out.is_file() or out.stat().st_size == 0:
        with contextlib.suppress(OSError):
            out.unlink(missing_ok=True)
        raise AudioNormalizeError("Decoded audio is empty.")

    return out, [out]
