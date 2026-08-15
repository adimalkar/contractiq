"""FastAPI dependency injection providers."""

import redis.asyncio as aioredis
import structlog
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from contractiq.config import Settings, get_settings
from contractiq.db.connection import get_db_session
from contractiq.db.repository import ContractRepository
from contractiq.pipeline.embedder import EmbeddingService
from contractiq.rag.engine import RAGEngine

logger = structlog.get_logger(__name__)

_redis_pool: aioredis.Redis | None = None
_embedder_instance: EmbeddingService | None = None


def get_embedder_service(settings: Settings = Depends(get_settings)) -> EmbeddingService:
    """Return shared embedding service instance."""
    global _embedder_instance
    if _embedder_instance is None:
        _embedder_instance = EmbeddingService(settings)
    return _embedder_instance


# Alias for dependency injection
get_embedder = get_embedder_service


async def get_repository(session: AsyncSession = Depends(get_db_session)) -> ContractRepository:
    """Provide scoped repository instance."""
    return ContractRepository(session)


async def get_rag_engine(
    session: AsyncSession = Depends(get_db_session),
    embedder: EmbeddingService = Depends(get_embedder_service),
    settings: Settings = Depends(get_settings),
) -> RAGEngine:
    """Provide fully wired RAG engine."""
    return RAGEngine(session, embedder, settings)


async def get_redis_client(settings: Settings = Depends(get_settings)) -> aioredis.Redis | None:
    """Provide async Redis client with fallback handling."""
    global _redis_pool
    if _redis_pool is None:
        try:
            _redis_pool = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
            await _redis_pool.ping()
        except Exception as e:
            logger.warning(
                "Redis connection unavailable, caching disabled or using in-memory", error=str(e)
            )
            _redis_pool = None
    return _redis_pool
