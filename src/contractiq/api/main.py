"""FastAPI Application Factory, Lifespan Management, Observability, and Route Mounting."""

from contextlib import asynccontextmanager
from pathlib import Path

import structlog
from fastapi import FastAPI, Request, status
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from prometheus_fastapi_instrumentator import Instrumentator
from slowapi.errors import RateLimitExceeded

from contractiq import __version__
from contractiq.api.middleware import setup_middleware
from contractiq.api.routes import (
    analytics_router,
    documents_router,
    health_router,
    query_router,
)
from contractiq.api.routes.compare import router as compare_router
from contractiq.api.routes.ws import router as ws_router
from contractiq.config import Settings, get_settings
from contractiq.db.connection import close_db, init_db
from contractiq.observability.tracing import setup_tracing
from contractiq.security.rate_limiter import custom_rate_limit_exceeded_handler, limiter

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and graceful shutdown lifecycle."""
    settings = get_settings()
    logger.info(
        "Initializing ContractIQ backend services", env=settings.APP_ENV, version=__version__
    )

    # Initialize Distributed Tracing
    setup_tracing(settings=settings)

    # Initialize Database Connection Pool
    await init_db(settings)

    yield

    logger.info("Shutting down ContractIQ backend services")
    await close_db()


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create and configure the production FastAPI application."""
    cfg = settings or get_settings()

    app = FastAPI(
        title="ContractIQ API",
        description="Production-grade AI Contract Intelligence, Agentic Workflows & Hybrid RAG Engine",
        version=__version__,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # Setup Rate Limiting State & Handlers
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, custom_rate_limit_exceeded_handler)

    # Setup Middleware
    setup_middleware(app, cfg.CORS_ORIGINS)

    # Setup Prometheus Metrics Instrumentator (/metrics)
    Instrumentator(
        should_group_status_codes=True,
        should_ignore_untemplated=True,
        excluded_handlers=["/metrics", "/health", "/docs", "/openapi.json"],
    ).instrument(app).expose(app, endpoint="/metrics", include_in_schema=True)

    # Mount API Routers
    app.include_router(health_router)
    app.include_router(query_router)
    app.include_router(documents_router)
    app.include_router(analytics_router)
    app.include_router(compare_router)
    app.include_router(ws_router)

    # Static UI Files Mounting
    static_dir = Path(__file__).parent.parent / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

        @app.get("/", include_in_schema=False)
        async def serve_dashboard() -> FileResponse:
            index_path = static_dir / "index.html"
            if index_path.exists():
                return FileResponse(str(index_path))
            return JSONResponse({"message": "ContractIQ API operational. Web Dashboard building."})

    # Global Exception Handlers
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        req_id = getattr(request.state, "request_id", "unknown")
        logger.error(
            "Unhandled API exception", error=str(exc), path=request.url.path, request_id=req_id
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "InternalServerError",
                "detail": "An unexpected error occurred while processing your request.",
                "request_id": req_id,
            },
        )

    return app


app = create_app()
