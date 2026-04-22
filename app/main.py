from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import router
from app.core.settings import get_settings
from app.database.initializer import initialize_datastores


settings = get_settings()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await initialize_datastores()
    yield


app = FastAPI(
    title=settings.app_name,
    debug=settings.app_debug,
    lifespan=lifespan,
)
app.include_router(router)
app.include_router(router, prefix=settings.api_prefix)


@app.get("/health")
async def healthcheck() -> dict[str, str]:
    return {"status": "ok"}
