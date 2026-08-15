"""API Key authentication middleware and JWT verification stubs."""

import structlog
from fastapi import Header, HTTPException, status

from contractiq.config import get_settings

logger = structlog.get_logger(__name__)


def verify_api_key(x_api_key: str | None = Header(default=None)) -> str | None:
    """Validate incoming X-API-Key against configured system secret."""
    settings = get_settings()

    if not settings.REQUIRE_AUTH:
        return x_api_key or "anonymous"

    if not x_api_key or x_api_key != settings.API_KEY:
        logger.warning("Unauthorized API key access attempt", provided_key=bool(x_api_key))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing X-API-Key authentication header.",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    return x_api_key
