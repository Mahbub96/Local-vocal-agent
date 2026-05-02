"""Best-effort removal of old TTS files so the audio directory cannot grow without bound."""

from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path

from app.core.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


def schedule_ephemeral_tts_delete(path: Path | None) -> None:
    """
    Delete a single synthesized WAV after ``tts_ephemeral_grace_seconds``.
    Assistant text remains in SQLite; Chroma embeddings are unchanged.
    """
    if path is None:
        return
    s = get_settings()
    if not s.tts_ephemeral:
        return
    delay = float(s.tts_ephemeral_grace_seconds)
    if delay < 5.0:
        delay = 5.0
    target = path.resolve()

    async def _run() -> None:
        await asyncio.sleep(delay)
        try:
            if target.is_file():
                target.unlink()
        except OSError as exc:
            logger.debug("Ephemeral TTS delete skipped %s: %s", target.name, exc)

    try:
        asyncio.get_running_loop().create_task(_run())
    except RuntimeError:
        logger.warning("Ephemeral TTS delete not scheduled (no asyncio loop): %s", target.name)


def cleanup_old_tts_files(
    *,
    max_age_seconds: float | None = None,
    max_files_to_scan: int = 5000,
) -> int:
    """
    Delete `*.wav` under ``tts_staging_dir`` older than retention.
    Returns number of files removed. Never raises.
    """
    age = max_age_seconds
    if age is None:
        age = float(settings.tts_retention_hours) * 3600.0
    if age <= 0:
        return 0

    base = settings.tts_staging_dir
    if not base.is_dir():
        return 0

    cutoff = time.time() - age
    removed = 0
    try:
        paths = list(base.glob("*.wav"))[:max_files_to_scan]
        for p in paths:
            try:
                if not p.is_file():
                    continue
                if p.stat().st_mtime < cutoff:
                    p.unlink(missing_ok=True)
                    removed += 1
            except OSError as exc:
                logger.debug("TTS cleanup skip %s: %s", p, exc)
    except Exception:
        logger.exception("TTS cleanup failed")
    return removed
