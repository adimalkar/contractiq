"""ContractIQ Observability: Distributed OpenTelemetry tracing and Prometheus metrics."""

from contractiq.observability.metrics import (
    CHUNKS_CREATED,
    DOCUMENTS_INGESTED,
    FAITHFULNESS_SCORE,
    HALLUCINATION_FLAGS,
    LLM_CALLS,
    LLM_LATENCY,
    LLM_TOKENS,
    PII_REDACTIONS,
    QUERY_COUNTER,
    QUERY_LATENCY,
    RETRIEVAL_CHUNKS,
    RETRIEVAL_SCORE,
)
from contractiq.observability.tracing import get_tracer, setup_tracing, traced

__all__ = [
    "setup_tracing",
    "get_tracer",
    "traced",
    "QUERY_COUNTER",
    "QUERY_LATENCY",
    "RETRIEVAL_CHUNKS",
    "RETRIEVAL_SCORE",
    "FAITHFULNESS_SCORE",
    "HALLUCINATION_FLAGS",
    "PII_REDACTIONS",
    "DOCUMENTS_INGESTED",
    "CHUNKS_CREATED",
    "LLM_CALLS",
    "LLM_TOKENS",
    "LLM_LATENCY",
]
