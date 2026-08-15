"""FastAPI Route Handlers."""

from contractiq.api.routes.analytics import router as analytics_router
from contractiq.api.routes.documents import router as documents_router
from contractiq.api.routes.health import router as health_router
from contractiq.api.routes.query import router as query_router

__all__ = [
    "health_router",
    "query_router",
    "documents_router",
    "analytics_router",
]
