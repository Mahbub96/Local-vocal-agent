from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.core.settings import get_settings
from app.database.initializer import initialize_datastores
from app.database.sqlite.session import close_db_engine


settings = get_settings()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await initialize_datastores()
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
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)
app.include_router(router, prefix=settings.api_prefix)


@app.get("/health")
async def healthcheck() -> dict[str, str]:
    return {"status": "ok"}
