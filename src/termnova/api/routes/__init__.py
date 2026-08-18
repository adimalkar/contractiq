from termnova.api.routes.analytics import router as analytics_router
from termnova.api.routes.documents import router as documents_router
from termnova.api.routes.graph import router as graph_router
from termnova.api.routes.health import router as health_router
from termnova.api.routes.query import router as query_router
from termnova.api.routes.workspaces import router as workspaces_router

__all__ = [
    "health_router",
    "query_router",
    "documents_router",
    "analytics_router",
    "graph_router",
    "workspaces_router",
]
