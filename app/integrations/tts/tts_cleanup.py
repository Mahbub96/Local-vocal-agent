"""Best-effort removal of old TTS files so the audio directory cannot grow without bound."""

from __future__ import annotations

import logging
import time
from pathlib import Path

from app.core.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


def cleanup_old_tts_files(
    *,
    max_age_seconds: float | None = None,
    max_files_to_scan: int = 5000,
) -> int:
    """
    Delete `*.wav` under `tts_output_dir` older than retention.
    Returns number of files removed. Never raises.
    """
    age = max_age_seconds
    if age is None:
        age = float(settings.tts_retention_hours) * 3600.0
    if age <= 0:
        return 0

    base = settings.tts_output_dir
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
