# Termnova — Production Observability & Telemetry Guide

This guide describes the OpenTelemetry distributed tracing and Prometheus metrics instrumentation in Termnova.

---

## 1. Metrics Architecture

Termnova exposes Prometheus metrics at `/metrics` using `prometheus-fastapi-instrumentator` and custom domain-specific collectors.

### Available Prometheus Metrics

| Metric Name | Type | Description | Labels |
|---|---|---|---|
| `termnova_queries_total` | Counter | Total RAG inquiries processed | `status`, `model` |
| `termnova_query_latency_seconds` | Histogram | End-to-end processing duration | N/A |
| `termnova_retrieval_chunks_count` | Histogram | Chunks retrieved by hybrid retriever | N/A |
| `termnova_retrieval_fused_score` | Histogram | RRF fused scores of retrieved chunks | N/A |
| `termnova_faithfulness_score` | Histogram | Claim entailment grounding scores | N/A |
| `termnova_hallucination_flags_total` | Counter | Unsupported claims detected by guardrails | `verdict` |
| `termnova_pii_redactions_total` | Counter | Sensitive PII terms redacted | `pii_type` |
| `termnova_documents_ingested_total` | Counter | Ingested contract documents | `status`, `file_type` |
| `termnova_chunks_created_total` | Counter | Total chunk vectors stored | N/A |
| `termnova_llm_calls_total` | Counter | Provider LLM API calls | `provider`, `model`, `purpose` |
| `termnova_llm_tokens_total` | Counter | Tokens consumed by LLMs | `direction` |
| `termnova_active_connections` | Gauge | Active WebSocket & SSE streams | N/A |

---

## 2. Distributed Tracing (OpenTelemetry)

OpenTelemetry tracing is initialized during FastAPI startup in `src/termnova/observability/tracing.py`.

### Span Hierarchy
```
[HTTP POST /api/v1/query]
  └─ [rag.query]
       ├─ [rewriter.rewrite]
       ├─ [retriever.retrieve]
       │    ├─ [repository.vector_search]
       │    └─ [bm25.search]
       ├─ [grader.grade_chunks]
       ├─ [generator.generate]
       └─ [guardrails.check]
            ├─ [pii_redactor]
            └─ [entailment_auditor]
```

---

## 3. Recommended PromQL Alert Rules

### High Hallucination Rate Alert
```promql
rate(termnova_hallucination_flags_total[5m]) / rate(termnova_queries_total[5m]) > 0.15
```

### High Latency Alert (p95 > 3.0s)
```promql
histogram_quantile(0.95, sum(rate(termnova_query_latency_seconds_bucket[5m])) by (le)) > 3.0
```
