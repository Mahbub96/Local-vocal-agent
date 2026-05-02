from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.database.chroma.client import get_memory_collection
from app.database.sqlite.base import Base
from app.database.sqlite.session import engine
from app.models import Message, Metadata, Session  # noqa: F401

# Single view for ad-hoc inspection: all rows from ``messages`` with session context (text chat log).
_CHAT_VIEW_SQL = """
CREATE VIEW IF NOT EXISTS chat AS
SELECT
  m.id AS message_id,
  m.session_id,
  m.role,
  m.content,
  m.content_type,
  m.sequence_number,
  m.created_at,
  s.title AS session_title,
  s.user_id AS session_user_id
FROM messages m
LEFT JOIN sessions s ON s.id = m.session_id
"""

# Applied on existing DBs (create_all does not alter existing tables).
_EXTRA_INDEX_STATEMENTS = (
    "CREATE INDEX IF NOT EXISTS idx_metadata_key_created_at ON metadata(key, created_at)",
    "CREATE INDEX IF NOT EXISTS idx_sessions_user_active_last "
    "ON sessions(user_id, is_active, last_message_at)",
)


async def initialize_sqlite_database(db_engine: AsyncEngine = engine) -> None:
    """
    Create all registered SQLite tables.

    Table definitions are imported by higher-level modules before startup.
    """
    async with db_engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
        await connection.execute(text(_CHAT_VIEW_SQL))
        for stmt in _EXTRA_INDEX_STATEMENTS:
            await connection.execute(text(stmt))


def initialize_chroma() -> None:
    """Ensure the primary Chroma collection exists."""
    get_memory_collection()


async def initialize_datastores() -> None:
    """Initialize all configured datastores."""
    await initialize_sqlite_database()
    initialize_chroma()
