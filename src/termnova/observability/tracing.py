"""OpenTelemetry distributed tracing setup, manual span helpers, and instrumentation."""

from collections.abc import Callable
from functools import wraps
from typing import Any

import structlog
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

from termnova.config import Settings, get_settings

logger = structlog.get_logger(__name__)
_tracer_initialized = False


def setup_tracing(
    service_name: str = "termnova", settings: Settings | None = None
) -> TracerProvider:
    """Configure OpenTelemetry TracerProvider with OTLP or console exporter."""
    global _tracer_initialized
    if _tracer_initialized:
        return trace.get_tracer_provider()  # type: ignore

    cfg = settings or get_settings()
    resource = Resource.create(
        {
            "service.name": cfg.OTEL_SERVICE_NAME or service_name,
            "service.version": "0.2.0",
            "deployment.environment": cfg.APP_ENV,
        }
    )

    provider = TracerProvider(resource=resource)

    if cfg.OTEL_EXPORTER_OTLP_ENDPOINT:
        try:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

            exporter = OTLPSpanExporter(endpoint=cfg.OTEL_EXPORTER_OTLP_ENDPOINT, insecure=True)
            provider.add_span_processor(BatchSpanProcessor(exporter))
            logger.info(
                "OpenTelemetry OTLP exporter configured", endpoint=cfg.OTEL_EXPORTER_OTLP_ENDPOINT
            )
        except Exception as e:
            logger.warning(
                "Failed to initialize OTLP exporter, falling back to console", error=str(e)
            )
            provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
    else:
        # In dev mode without OTLP endpoint, register provider with noop or console
        pass

    trace.set_tracer_provider(provider)
    _tracer_initialized = True
    return provider


def get_tracer(name: str = "termnova") -> trace.Tracer:
    """Return a named tracer."""
    return trace.get_tracer(name)


def traced(span_name: str | None = None) -> Callable:
    """Decorator to trace async functions with an OpenTelemetry child span."""

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            tracer = get_tracer("termnova.pipeline")
            name = span_name or func.__name__
            with tracer.start_as_current_span(name) as span:
                span.set_attribute("function.name", func.__name__)
                try:
                    result = await func(*args, **kwargs)
                    return result
                except Exception as e:
                    span.record_exception(e)
                    span.set_status(trace.StatusCode.ERROR, str(e))
                    raise

        return wrapper

    return decorator
