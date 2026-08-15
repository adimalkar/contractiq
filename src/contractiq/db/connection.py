"""Database engine and async session management with multi-loop test resiliency."""

import asyncio
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
)
from sqlalchemy.ext.asyncio import (
    create_async_engine as _create_async_engine,
)
from sqlalchemy.pool import NullPool

from contractiq.config import Settings, get_settings

_engine: AsyncEngine | None = None
_engine_loop: asyncio.AbstractEventLoop | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def create_async_engine(settings: Settings | None = None) -> AsyncEngine:
    """Create and return a configured AsyncEngine instance."""
    cfg = settings or get_settings()
    pool_class = NullPool if cfg.APP_ENV == "test" else None

    kwargs = {
        "pool_recycle": 3600,
        "pool_pre_ping": True,
    }
    if pool_class is not None:
        kwargs["poolclass"] = pool_class
    else:
        kwargs["pool_size"] = cfg.DB_POOL_SIZE
        kwargs["max_overflow"] = cfg.DB_MAX_OVERFLOW

    return _create_async_engine(cfg.DATABASE_URL, **kwargs)


def AsyncSessionFactory(engine: AsyncEngine | None = None) -> async_sessionmaker[AsyncSession]:
    """Return an async_sessionmaker bound to the given engine or current event loop."""
    global _session_factory, _engine, _engine_loop
    if engine is not None:
        return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    current_loop = asyncio.get_event_loop()
    if _session_factory is None or _engine is None or _engine_loop != current_loop:
        _engine = create_async_engine()
        _engine_loop = current_loop
        _session_factory = async_sessionmaker(_engine, expire_on_commit=False, class_=AsyncSession)

    return _session_factory


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields an isolated AsyncSession per request."""
    factory = AsyncSessionFactory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db(settings: Settings | None = None) -> None:
    """Initialize database engine and session factory on app startup."""
    global _engine, _session_factory, _engine_loop
    current_loop = asyncio.get_event_loop()
    _engine = create_async_engine(settings)
    _engine_loop = current_loop
    _session_factory = async_sessionmaker(_engine, expire_on_commit=False, class_=AsyncSession)


async def close_db() -> None:
    """Dispose of the database engine on application shutdown."""
    global _engine, _session_factory, _engine_loop
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None
        _engine_loop = None
