# ContractIQ — Production Observability & Telemetry Guide

This guide describes the OpenTelemetry distributed tracing and Prometheus metrics instrumentation in ContractIQ.

---

## 1. Metrics Architecture

ContractIQ exposes Prometheus metrics at `/metrics` using `prometheus-fastapi-instrumentator` and custom domain-specific collectors.

### Available Prometheus Metrics

| Metric Name | Type | Description | Labels |
|---|---|---|---|
| `contractiq_queries_total` | Counter | Total RAG inquiries processed | `status`, `model` |
| `contractiq_query_latency_seconds` | Histogram | End-to-end processing duration | N/A |
| `contractiq_retrieval_chunks_count` | Histogram | Chunks retrieved by hybrid retriever | N/A |
| `contractiq_retrieval_fused_score` | Histogram | RRF fused scores of retrieved chunks | N/A |
| `contractiq_faithfulness_score` | Histogram | Claim entailment grounding scores | N/A |
| `contractiq_hallucination_flags_total` | Counter | Unsupported claims detected by guardrails | `verdict` |
| `contractiq_pii_redactions_total` | Counter | Sensitive PII terms redacted | `pii_type` |
| `contractiq_documents_ingested_total` | Counter | Ingested contract documents | `status`, `file_type` |
| `contractiq_chunks_created_total` | Counter | Total chunk vectors stored | N/A |
| `contractiq_llm_calls_total` | Counter | Provider LLM API calls | `provider`, `model`, `purpose` |
| `contractiq_llm_tokens_total` | Counter | Tokens consumed by LLMs | `direction` |
| `contractiq_active_connections` | Gauge | Active WebSocket & SSE streams | N/A |

---

## 2. Distributed Tracing (OpenTelemetry)

OpenTelemetry tracing is initialized during FastAPI startup in `src/contractiq/observability/tracing.py`.

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
rate(contractiq_hallucination_flags_total[5m]) / rate(contractiq_queries_total[5m]) > 0.15
```

### High Latency Alert (p95 > 3.0s)
```promql
histogram_quantile(0.95, sum(rate(contractiq_query_latency_seconds_bucket[5m])) by (le)) > 3.0
```
