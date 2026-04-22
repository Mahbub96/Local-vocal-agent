from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from app.database.sqlite.session import get_db_session


async def get_async_db_session() -> AsyncGenerator[AsyncSession, None]:
    async for session in get_db_session():
        yield session
