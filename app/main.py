from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.core.settings import get_settings
from app.database.initializer import initialize_datastores
from app.database.sqlite.session import close_db_engine
from app.integrations.tts.tts_cleanup import cleanup_old_tts_files
from app.integrations.tts.tts_preload import run_speech_startup_pipeline_sync


settings = get_settings()
_log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await initialize_datastores()
    try:
        n = cleanup_old_tts_files()
        if n:
            _log.info("Removed %s stale TTS file(s) on startup", n)
    except Exception:
        _log.exception("TTS cleanup on startup failed")
    if settings.tts_preload_on_startup or settings.warm_speech_models_on_startup:

        async def _speech_startup() -> None:
            try:
                await asyncio.to_thread(run_speech_startup_pipeline_sync)
            except Exception as exc:
                if "espeak" in str(exc).lower():
                    _log.warning(
                        "Speech preload pipeline: %s. For VITS, install eSpeak (e.g. brew install espeak-ng).",
                        exc,
                    )
                else:
                    _log.exception("Speech preload / warm-up on startup failed")

        _speech_startup_task = asyncio.create_task(_speech_startup())
    yield
    await close_db_engine()


app = FastAPI(
    title=settings.app_name,
    debug=settings.app_debug,
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins,
    # Direct browser access to API:8000 from LAN (e.g. custom VITE_API_BASE with machine IP).
    allow_origin_regex=r"http://(192\.168\.\d{1,3}\.\d{1,3}|10\.\d{1,3}\.\d{1,3}\.\d{1,3}|172\.(1[6-9]|2\d|3[0-1])\.\d{1,3}\.\d{1,3})(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)
app.include_router(router, prefix=settings.api_prefix)


@app.get("/health")
async def healthcheck() -> dict[str, str]:
    return {"status": "ok"}
