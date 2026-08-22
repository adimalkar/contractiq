"""Redis caching wrapper for cross-contract intelligence and portfolio aggregations."""

import hashlib
import json
import uuid
from typing import Any

import redis.asyncio as aioredis
import structlog

logger = structlog.get_logger(__name__)


class IntelligenceCache:
    """Provides tenant-isolated caching with automatic invalidation for expensive portfolio queries."""

    CACHE_PREFIX = "ciq:intelligence"
    DEFAULT_TTL = 300  # 5 minutes

    @classmethod
    def build_key(
        cls,
        query_type: str,
        org_id: uuid.UUID | None = None,
        params: dict[str, Any] | None = None,
    ) -> str:
        """Construct a deterministic cache key scoped to tenant organization."""
        org_str = str(org_id) if org_id else "global"
        params_json = json.dumps(params or {}, sort_keys=True)
        params_hash = hashlib.md5(params_json.encode("utf-8")).hexdigest()[:12]
        return f"{cls.CACHE_PREFIX}:{org_str}:{query_type}:{params_hash}"

    @classmethod
    async def get(
        cls,
        cache_key: str,
        redis_client: aioredis.Redis | None,
    ) -> dict[str, Any] | list[Any] | None:
        """Fetch and deserialize cached intelligence payload if Redis is available."""
        if not redis_client:
            return None

        try:
            cached = await redis_client.get(cache_key)
            if cached:
                logger.debug("Intelligence cache HIT", key=cache_key)
                return json.loads(cached)
        except Exception as e:
            logger.warning("Intelligence cache read error", error=str(e))
        return None

    @classmethod
    async def set(
        cls,
        cache_key: str,
        data: Any,
        redis_client: aioredis.Redis | None,
        ttl: int = DEFAULT_TTL,
    ) -> None:
        """Serialize and persist intelligence data in Redis with TTL expiration."""
        if not redis_client:
            return

        try:
            # Handle Pydantic models or raw dicts
            if hasattr(data, "model_dump"):
                serialized = json.dumps(data.model_dump(mode="json"))
            elif hasattr(data, "dict"):
                serialized = json.dumps(data.dict())
            else:
                serialized = json.dumps(data)

            await redis_client.setex(cache_key, ttl, serialized)
            logger.debug("Intelligence cache SET", key=cache_key, ttl=ttl)
        except Exception as e:
            logger.warning("Intelligence cache write error", error=str(e))

    @classmethod
    async def invalidate_org(
        cls,
        org_id: uuid.UUID | None,
        redis_client: aioredis.Redis | None,
    ) -> int:
        """Purge all cached intelligence entries for an organization upon document changes."""
        if not redis_client:
            return 0

        org_str = str(org_id) if org_id else "global"
        pattern = f"{cls.CACHE_PREFIX}:{org_str}:*"
        deleted_count = 0

        try:
            keys = await redis_client.keys(pattern)
            if keys:
                deleted_count = await redis_client.delete(*keys)
                logger.info("Intelligence cache invalidated", org=org_str, count=deleted_count)
        except Exception as e:
            logger.warning("Intelligence cache invalidation error", error=str(e))

        return deleted_count
