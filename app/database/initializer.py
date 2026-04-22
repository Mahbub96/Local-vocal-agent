from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncEngine

from app.database.chroma.client import get_memory_collection
from app.database.sqlite.base import Base
from app.database.sqlite.session import engine
from app.models import Message, Metadata, Session  # noqa: F401


async def initialize_sqlite_database(db_engine: AsyncEngine = engine) -> None:
    """
    Create all registered SQLite tables.

    Table definitions are imported by higher-level modules before startup.
    """
    async with db_engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)


def initialize_chroma() -> None:
    """Ensure the primary Chroma collection exists."""
    get_memory_collection()


async def initialize_datastores() -> None:
    """Initialize all configured datastores."""
    await initialize_sqlite_database()
    initialize_chroma()
