"""Prometheus custom business and telemetry metrics for Termnova."""

from prometheus_client import Counter, Gauge, Histogram

# ── RAG Query Metrics ──
QUERY_COUNTER = Counter(
    "termnova_queries_total",
    "Total RAG queries processed",
    ["status", "model"],
)

QUERY_LATENCY = Histogram(
    "termnova_query_latency_seconds",
    "End-to-end RAG query processing latency in seconds",
    buckets=[0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 3.0, 5.0, 10.0],
)

# ── Retrieval Quality Metrics ──
RETRIEVAL_CHUNKS = Histogram(
    "termnova_retrieval_chunks_count",
    "Number of candidate chunks retrieved per query",
    buckets=[0, 1, 2, 5, 10, 15, 20],
)

RETRIEVAL_SCORE = Histogram(
    "termnova_retrieval_fused_score",
    "Fused Reciprocal Rank Fusion score distribution",
    buckets=[0.1, 0.2, 0.4, 0.6, 0.8, 1.0],
)

# ── Guardrails & Responsible AI Metrics ──
FAITHFULNESS_SCORE = Histogram(
    "termnova_faithfulness_score",
    "Distribution of answer faithfulness scores from entailment auditor",
    buckets=[0.1, 0.3, 0.5, 0.7, 0.85, 0.95, 1.0],
)

HALLUCINATION_FLAGS = Counter(
    "termnova_hallucination_flags_total",
    "Total count of ungrounded or extrapolated claims detected",
    ["verdict"],
)

PII_REDACTIONS = Counter(
    "termnova_pii_redactions_total",
    "Total sensitive PII terms detected and redacted",
    ["pii_type"],
)

# ── Ingestion & Document Pipeline Metrics ──
DOCUMENTS_INGESTED = Counter(
    "termnova_documents_ingested_total",
    "Total contract documents uploaded and parsed",
    ["status", "file_type"],
)

CHUNKS_CREATED = Counter(
    "termnova_chunks_created_total",
    "Total vector chunks created and stored in PostgreSQL",
)

# ── LLM Token & Cost Tracking ──
LLM_CALLS = Counter(
    "termnova_llm_calls_total",
    "Total LLM API invocations",
    ["provider", "model", "purpose"],
)

LLM_TOKENS = Counter(
    "termnova_llm_tokens_total",
    "Total LLM tokens consumed",
    ["direction"],  # "prompt" or "completion"
)

LLM_LATENCY = Histogram(
    "termnova_llm_latency_seconds",
    "Raw LLM provider call latency",
    ["provider"],
    buckets=[0.2, 0.5, 1.0, 2.0, 4.0, 8.0],
)

# ── Real-Time Concurrency ──
ACTIVE_CONNECTIONS = Gauge(
    "termnova_active_connections",
    "Current active WebSocket and SSE client connections",
)
