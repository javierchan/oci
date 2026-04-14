"""Database engine and session helpers for the FastAPI application."""

from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.engine import URL, make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings

settings = get_settings()

engine = create_async_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_size=settings.DATABASE_POOL_SIZE,
    max_overflow=settings.DATABASE_MAX_OVERFLOW,
)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_db() -> AsyncIterator[AsyncSession]:
    """Yield an async SQLAlchemy session for a single request."""

    async with AsyncSessionLocal() as session:
        yield session


def get_sync_database_url() -> str:
    """Translate the configured async database URL into a sync driver URL."""

    url = make_url(settings.DATABASE_URL)
    host = "127.0.0.1" if url.host == "localhost" else url.host
    if url.drivername == "postgresql+asyncpg":
        sync_url = URL.create(
            drivername="postgresql+psycopg2",
            username=url.username,
            password=url.password,
            host=host,
            port=url.port,
            database=url.database,
            query=url.query,
        )
        return sync_url.render_as_string(hide_password=False)
    return str(url)
