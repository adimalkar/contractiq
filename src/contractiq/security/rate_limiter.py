"""SlowAPI rate limiting configuration and customized HTTP 429 handlers."""

from fastapi import Request, Response
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.responses import JSONResponse

from contractiq.config import get_settings

settings = get_settings()

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[settings.RATE_LIMIT_DEFAULT],
    storage_uri=settings.REDIS_URL,
)


def custom_rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> Response:
    """Return structured JSON error response on rate limit violation."""
    return JSONResponse(
        status_code=429,
        content={
            "error": "RateLimitExceeded",
            "message": f"Too many requests. Rate limit exceeded: {exc.detail}",
            "retry_after": getattr(exc, "retry_after", 60),
        },
        headers={"Retry-After": str(getattr(exc, "retry_after", 60))},
    )
