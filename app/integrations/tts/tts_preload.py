"""Coqui checkpoint download and optional Whisper/TTS warm-up (``run_speech_startup_pipeline_sync``)."""

from __future__ import annotations

import contextlib
import io
import logging

from app.core.settings import get_settings

logger = logging.getLogger(__name__)

_ESPEAK_HINT = (
    "Coqui English VITS needs eSpeak on your system — macOS: brew install espeak-ng | "
    "Ubuntu/Debian: sudo apt install espeak-ng"
)


def _is_espeak_missing(exc: BaseException) -> bool:
    msg = str(exc).lower()
    return "espeak" in msg and ("backend" in msg or "not found" in msg or "install" in msg)


def _run_with_suppressed_stdio(fn, *args, **kwargs):
    """
    Coqui prints model banners/progress to stdout/stderr during warm-up.
    Keep startup logs concise while preserving our structured logger output.
    """
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        return fn(*args, **kwargs)


def _warm_coqui(label: str, loader) -> None:
    try:
        _run_with_suppressed_stdio(loader)
    except Exception as exc:
        if _is_espeak_missing(exc):
            logger.warning("TTS warm-up skipped (%s): %s. %s", label, exc, _ESPEAK_HINT)
            return
        logger.exception("%s Coqui TTS warm-up failed", label.capitalize())


def predownload_coqui_models_sync() -> None:
    """
    Fetch default English TTS + its default vocoder, and Bangla TTS if configured.

    Uses ``TTS.download_model_by_name`` with an empty model init so only ``ModelManager``
    runs (same as first synthesis, but can run at startup).
    """
    from TTS.api import TTS

    settings = get_settings()
    from app.integrations.tts.coqui_tts import resolve_local_coqui_paths

    api = _run_with_suppressed_stdio(TTS, model_name="", progress_bar=False, gpu=False)

    logger.info("TTS preload: downloading %s (and default vocoder if any)", settings.tts_model_name)
    try:
        if resolve_local_coqui_paths(settings.tts_model_name) is None:
            _run_with_suppressed_stdio(api.download_model_by_name, settings.tts_model_name)
        else:
            logger.info("TTS preload: %s is a local bundle — skip hub download", settings.tts_model_name)
    except Exception as exc:
        logger.warning("TTS preload failed for %s: %s", settings.tts_model_name, exc)

    bn = (settings.tts_model_name_bn or "").strip()
    if bn:
        if resolve_local_coqui_paths(bn) is not None:
            logger.info("TTS preload: %s is a local bundle — skip hub download", bn)
        else:
            logger.info("TTS preload: downloading %s", bn)
            try:
                _run_with_suppressed_stdio(api.download_model_by_name, bn)
            except Exception as exc:
                logger.warning("TTS preload failed for %s: %s", bn, exc)

    logger.info("TTS preload: done")


def warm_speech_models_sync() -> None:
    """Load shared Whisper + Coqui instances so first voice/chat is not cold."""
    from app.integrations.stt.whisper_stt import get_whisper_stt
    from app.integrations.tts.coqui_tts import get_bangla_coqui_tts, get_default_coqui_tts

    settings = get_settings()
    logger.info("Speech warm-up: loading Whisper")
    try:
        get_whisper_stt().warm_load()
    except Exception:
        logger.exception("Whisper warm-up failed")

    logger.info(
        "Speech warm-up: loading default (English) Coqui TTS — %s",
        settings.tts_model_name,
    )
    _warm_coqui("default english", get_default_coqui_tts().warm_load)

    bn = (settings.tts_model_name_bn or "").strip()
    if bn and settings.warm_bangla_tts_on_startup:
        logger.info(
            "Speech warm-up: loading Bangla Coqui TTS — %s (Coqui may print a second 'vits' banner; that is expected.)",
            bn,
        )
        _warm_coqui("bangla", get_bangla_coqui_tts(bn).warm_load)
    elif bn and not settings.warm_bangla_tts_on_startup:
        logger.info(
            "Speech warm-up: skipping Bangla load at startup "
            "(warm_bangla_tts_on_startup=false); first Bangla synthesis will load %s.",
            bn,
        )
    logger.info("Speech warm-up: finished (some models may be skipped if dependencies are missing)")


def run_speech_startup_pipeline_sync() -> None:
    """Download weights (if enabled) then optionally load models — single background thread."""
    settings = get_settings()
    if settings.tts_preload_on_startup:
        predownload_coqui_models_sync()
    if settings.warm_speech_models_on_startup:
        warm_speech_models_sync()
