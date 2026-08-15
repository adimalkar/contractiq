<div align="center">

# 📑 ContractIQ
### Production-Grade AI Contract Intelligence Platform with Hybrid RAG, LangGraph Agents & Responsible AI Guardrails

[![Python Version](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.14-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![LangGraph](https://img.shields.io/badge/LangGraph-Agentic%20RAG-FF6F00.svg)](https://github.com/langchain-ai/langgraph)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16%20(pgvector)-336791.svg?logo=postgresql&logoColor=white)](https://github.com/pgvector/pgvector)
[![Celery](https://img.shields.io/badge/Celery-Distributed%20Tasks-37814A.svg?logo=celery&logoColor=white)](https://docs.celeryq.dev)
[![OpenTelemetry](https://img.shields.io/badge/OpenTelemetry-Tracing%20%26%20Metrics-F54C00.svg?logo=opentelemetry&logoColor=white)](https://opentelemetry.io)
[![Redis](https://img.shields.io/badge/Redis-7.0-DC382D.svg?logo=redis&logoColor=white)](https://redis.io)
[![CI Pipeline](https://img.shields.io/badge/CI-GitHub%20Actions-2088FF.svg?logo=githubactions&logoColor=white)](https://github.com/adimalkar/contractiq)
[![Coverage](https://img.shields.io/badge/Tests-39%20Passed%20(100%25)-brightgreen.svg)](https://pytest.org)
[![License](https://img.shields.io/badge/License-MIT-purple.svg)](LICENSE)

<p align="center">
  <strong>Grounded enterprise contract analysis combining dense semantic embeddings, BM25 keyword matching, Reciprocal Rank Fusion (RRF), Cross-Encoder re-ranking, LangGraph multi-step agents, clause-by-clause comparison, and automated hallucination guardrails.</strong>
</p>

</div>

---

## 📌 Problem Statement

Enterprises manage thousands of high-stakes vendor agreements, Master Services Agreements (MSAs), Statements of Work (SOWs), SLAs, and commercial leases across procurement, finance, and legal departments. Traditional search tools fail on complex legal inquiries like *"Which agreements have auto-renewal notice windows under 60 days?"* or *"What is our aggregate liability exposure across all cloud providers?"*.

Conversely, naive single-pass RAG systems frequently hallucinate terms, lose clause context, fail on exact contract identifiers (`SOW-2024-08`), and leak sensitive PII.

**ContractIQ** is an end-to-end, production-ready AI platform engineered to parse, index, retrieve, evaluate, compare, and audit enterprise contracts with **100% evidence-grounded answers** and sub-second query latency.

---

## 🏛️ System Architecture

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                                    ContractIQ v2                                       │
│                                                                                        │
│  ┌──────────────────┐    ┌─────────────────────┐    ┌───────────────────────────────┐  │
│  │   Web Dashboard  │    │  FastAPI REST / WS  │    │  Distributed Ingestion Queue  │  │
│  │ (Dark Glass SPA) │◄──►│    (/api/v1/, /ws/) │◄───│   (Celery Workers + Redis)    │  │
│  └────────┬─────────┘    └──────────┬──────────┘    └───────────────┬───────────────┘  │
│           │                         │                               │                  │
│           ▼                         ▼                               ▼                  │
│  ┌──────────────────────────────────────────────────────────────────────────────────┐  │
│  │                              Agentic RAG Engine                                  │  │
│  │                                                                                  │  │
│  │   ┌──────────────────────────────────────────────────────────────────────────┐   │  │
│  │   │ LangGraph StateGraph Workflow                                            │   │  │
│  │   │  ├─ Intent Classifier & Multi-Part Query Decomposer                      │   │  │
│  │   │  ├─ Contextual Rewriter & Hypothetical Document Embeddings (HyDE)        │   │  │
│  │   │  └─ Self-Correction & Query Reformulation Loops (max 2 retries)          │   │  │
│  │   └────────────────────────────────────┬─────────────────────────────────────┘   │  │
│  │                                        ▼                                         │  │
│  │   ┌──────────────────────────────────────────────────────────────────────────┐   │  │
│  │   │ Two-Stage Hybrid Retrieval                                               │   │  │
│  │   │  ├─ Stage 1 (Fast Recall): Dense pgvector + Sparse BM25 via RRF (k=60)   │   │  │
│  │   │  └─ Stage 2 (Precision): Cross-Encoder Re-Ranking with MMR Diversity     │   │  │
│  │   └────────────────────────────────────┬─────────────────────────────────────┘   │  │
│  │                                        ▼                                         │  │
│  │   ┌──────────────────────────────────────────────────────────────────────────┐   │  │
│  │   │ Relevance Grader & Citation-Grounded Generator                           │   │  │
│  │   │  └─ Filters context noise & formats [Source N] tags to Doc, Page, Clause │   │  │
│  │   └────────────────────────────────────┬─────────────────────────────────────┘   │  │
│  │                                        ▼                                         │  │
│  │   ┌──────────────────────────────────────────────────────────────────────────┐   │  │
│  │   │ Responsible AI Guardrails                                                │   │  │
│  │   │  ├─ Propositional Claim-Level Entailment Auditor (Hallucination Defense) │   │  │
│  │   │  ├─ PII Redaction Engine (SSN, Email, Phone, Credit Cards)               │   │  │
│  │   │  └─ Multi-Factor Confidence Scorer (0.3 Retr + 0.3 Rel + 0.4 Faith)      │   │  │
│  │   └────────────────────────────────────┬─────────────────────────────────────┘   │  │
│  │                                        ▼                                         │  │
│  │   ┌──────────────────────────────────────────────────────────────────────────┐   │  │
│  │   │ Contract Comparison & Redline Diff Engine                                │   │  │
│  │   │  ├─ Semantic Clause Alignment (Hungarian Matching on Vector Similarity)  │   │  │
│  │   │  └─ Word-Level Inline HTML Diffing & Financial Discrepancy Extraction    │   │  │
│  │   └──────────────────────────────────────────────────────────────────────────┘   │  │
│  └────────────────────────────────────────┬─────────────────────────────────────────┘  │
│                                           ▼                                            │
│  ┌──────────────────────────────────────────────────────────────────────────────────┐  │
│  │ Infrastructure: PostgreSQL (pgvector) │ Redis │ Celery │ Flower │ OTEL Collector │  │
│  └──────────────────────────────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## ⚡ Key Features & Engineering Innovations

| Feature | Description |
|---|---|
| 🤖 **LangGraph Agentic RAG** | Multi-step stateful reasoning graph with intent classification, multi-part decomposition, self-correction loops on poor relevance, and maximum retry bounds. |
| 🔍 **Two-Stage Hybrid Retrieval** | Fuses dense vector cosine similarity (pgvector) with BM25 keyword matching via Reciprocal Rank Fusion (RRF $k=60$), followed by Cross-Encoder secondary re-ranking with Maximal Marginal Relevance (MMR) diversity. |
| 🔄 **Contextual Memory & HyDE** | Resolves follow-up relative queries across conversation turns and expands vague prompts with Hypothetical Document Embeddings. |
| ⚡ **Async Distributed Ingestion** | Background Celery task processing with Redis broker and Flower monitoring dashboard (`:5555`) for non-blocking OCR and vectorization. |
| 📊 **Full Observability Suite** | OpenTelemetry distributed tracing across all pipeline stages + Prometheus `/metrics` endpoint tracking query latency, token usage, and hallucination rates. |
| 📑 **Clause Comparison & Diffing** | Semantic clause alignment pairing corresponding sections across agreements with inline redline diffs and automated financial discrepancy extraction. |
| 🏷️ **Evidence-Grounded Citations** | Every factual claim links to interactive `[Source N]` tags mapped to document filename, page number, and original chunk excerpts in a slide-out drawer. |
| 🛡️ **Responsible AI Guardrails** | Propositional claim entailment audit, sensitive PII redaction (SSNs, emails, phone numbers), and composite confidence scoring. |
| 🌐 **WebSocket Live Streaming** | Bidirectional WebSocket channel (`/ws/query`, `/ws/notifications`) with real-time token streaming and ingestion progress alerts. |
| 🔒 **Security & Rate Limiting** | SlowAPI rate limiting (20 req/min for RAG queries) and API key authentication middleware. |

---

## 🚀 Quick Start

### 1. Installation
```bash
# Clone the repository
git clone https://github.com/adimalkar/contractiq.git
cd contractiq

# Create virtual environment & install dependencies
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip setuptools wheel
pip install -e ".[all]"

# Copy environment configuration
cp .env.example .env
```

### 2. Launch Development Stack
```bash
# Start FastAPI application
make dev

# Start background Celery worker (in separate terminal)
make worker
```
- **Web Dashboard:** `http://localhost:8000`
- **Interactive OpenAPI Docs:** `http://localhost:8000/docs`
- **Prometheus Metrics:** `http://localhost:8000/metrics`

### 3. Full Multi-Container Docker Stack
```bash
docker compose up -d
```
Starts PostgreSQL+pgvector, Redis, FastAPI App, Celery Worker, Flower Dashboard (`:5555`), and OpenTelemetry Collector (`:4317`).

---

## 🧪 Testing & Verification

```bash
# Run all unit and integration tests
make test

# Run full test suite with coverage report
make test-cov

# Execute Locust load test (20 concurrent users)
make load-test

# Run RAGAS quantitative benchmark evaluation
make evaluate
```

---

## 📡 REST & WebSocket API Reference

| Endpoint | Method | Description |
|---|---|---|
| `/health` | `GET` | System health, database readiness, and active provider status |
| `/metrics` | `GET` | Prometheus telemetry and business metrics |
| `/api/v1/query` | `POST` | Execute hybrid / agentic RAG query with citations and guardrails |
| `/api/v1/query/{id}` | `GET` | Retrieve audit details and citations for a past inquiry |
| `/api/v1/documents` | `GET` | List all indexed contracts with chunk counts |
| `/api/v1/documents/upload` | `POST` | Upload and parse PDF/DOCX contract with automatic vectorization |
| `/api/v1/compare` | `POST` | Compare two contracts side-by-side with clause alignment and diffs |
| `/api/v1/analytics/usage` | `GET` | Operational throughput, mean latency, and top asked questions |
| `/api/v1/analytics/quality` | `GET` | Responsible AI guardrails, hallucination rates, and score distributions |
| `/ws/query` | `WS` | Bidirectional WebSocket streaming Q&A |
| `/ws/notifications` | `WS` | Real-time push notifications for ingestion and system events |

---

## 👤 Author & Portfolio

**Aditya Malkar**  
AI Engineer | MS Data Science (Stevens Institute of Technology)  
- **Email:** [adityamalkar0@gmail.com](mailto:adityamalkar0@gmail.com)  
- **GitHub:** [@adimalkar](https://github.com/adimalkar)  
- **LinkedIn:** [Aditya Malkar](https://linkedin.com/in/aditya-malkar)
