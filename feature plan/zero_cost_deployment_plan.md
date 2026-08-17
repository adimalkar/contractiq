# Termnova — $0 Zero-Cost Cloud Deployment & Architecture Plan

## 1. Executive Summary & Objective

This document outlines a **100% Free-Tier ($0/month)** production deployment architecture for **Termnova**. It is designed specifically to support all foundational features (Phase 1–6) and product modules (Feature Plans 1–5: Visualizer, Collaborative Workspace, Contract Inbox, Negotiation Tracker, and Cross-Contract Intelligence) without incurring cloud hosting fees.

---

## 2. Zero-Cost ($0/Month) Tech Stack Matrix

| Component | Free-Tier Provider | Free Quota / Capabilities | Why Chosen for Termnova |
|---|---|---|---|
| **App Compute (FastAPI + WebSockets)** | **Render Free** or **Koyeb Free** or **Hugging Face Spaces** | 512 MB RAM, free TLS/SSL, Docker runtime, WebSockets | Hosts FastAPI, serves static UI, handles WebSocket rooms |
| **Vector Database** | **Neon PostgreSQL** or **Supabase** | 0.5 GB storage, native `pgvector`, serverless pooling | Zero-cost managed Postgres with vector indexing for RAG & Graph |
| **Cache & Task Broker** | **Upstash Redis** | 10,000 commands/day, TLS, standard Redis URL | Zero-cost serverless Redis for query caching & rate limiting |
| **Async Background Tasks** | **In-Process FastAPI `BackgroundTasks` + APScheduler** | Unlimited in-memory / local event loop | Eliminates need for separate paid Celery worker instances |
| **Email Notifications** | **Resend** or **Gmail SMTP** | 3,000 emails/month free (Resend) or 500/day (Gmail) | Deadline alerts, renewal reminders, triage routing notifications |
| **Object / File Storage** | **Local Disk (`data/uploads`)** or **Cloudflare R2** | 10 GB free R2 storage, $0 egress fees | Stores contract PDFs & exported negotiation reports |
| **Alternative: Host from Local Machine** | **Cloudflare Zero Trust Tunnel** | 100% Free, Unlimited RAM/CPU, Auto-HTTPS, custom domain | Uses your local 1TB drive & CPU with enterprise-grade edge CDN |

---

## 3. Deployment Architecture Diagram ($0 Cloud)

```
                              ┌──────────────────────────────────────────────────┐
                              │                 Web Browser                      │
                              │       (Desktop / Mobile HTTPS & WSS)             │
                              └────────────────────────┬─────────────────────────┘
                                                       │
                                          HTTPS & Secure WebSockets
                                                       │
                                                       ▼
                              ┌──────────────────────────────────────────────────┐
                              │             Render / Koyeb Free Compute          │
                              │  ┌────────────────────────────────────────────┐  │
                              │  │           FastAPI Gateway (Uvicorn)         │  │
                              │  │  • Static UI (D3.js Graph, Inbox, Chats)   │  │
                              │  │  • WebSocket Manager (Workspace Broadcast) │  │
                              │  │  • Hybrid RAG & Agentic Reasoner           │  │
                              │  │  • In-Process APScheduler (Daily Deadlines)│  │
                              │  └──────────────────────┬─────────────────────┘  │
                              └─────────────────────────┼────────────────────────┘
                                                        │
                    ┌───────────────────────────────────┼───────────────────────────────────┐
                    │                                   │                                   │
                    ▼                                   ▼                                   ▼
   ┌─────────────────────────────────┐ ┌─────────────────────────────────┐ ┌─────────────────────────────────┐
   │         Neon PostgreSQL         │ │          Upstash Redis          │ │        Resend / Gmail SMTP      │
   │  • `pgvector` embeddings        │ │  • Query response cache (TTL)   │ │  • Urgent contract alerts       │
   │  • Tenant & User tables (Auth)  │ │  • Intelligence aggregations    │ │  • Obligation reminder emails   │
   │  • Graph relationships & triage │ │  • Rate limiting buckets        │ │  • Workspace invite emails      │
   │  • 100% Free Tier (0.5GB)       │ │  • 100% Free (10k cmd/day)      │ │  • 100% Free (3k emails/mo)     │
   └─────────────────────────────────┘ └─────────────────────────────────┘ └─────────────────────────────────┘
```

---

## 4. Phase-by-Phase Deployment Alignment

To ensure deployment remains 100% free and functional as new features are implemented, the infrastructure adapts to each phase:

### Phase 1: Foundation (Auth, RBAC, Multi-Tenancy & Alembic)
* **Compute Impact**: Minimal CPU overhead; JWT stateless validation requires 0 additional RAM.
* **Database Strategy**: Database migrations run on container startup using entrypoint script (`alembic upgrade head` before `uvicorn`).
* **Connection Pooling**: Serverless Neon DB connection string with `?sslmode=require` and pool sizing set to `DB_POOL_SIZE=3` to stay well within free connection limits.

### Phase 2: Contract Lifecycle (Obligations, Risk & Calendar)
* **Background Tasks**: Instead of spinning up a separate paid worker container for Celery, run daily deadline checking via **APScheduler** inside the FastAPI lifespan context, writing notifications to the database.
* **Storage**: Extracted metadata and risk scores stored in PostgreSQL `JSONB` columns (negligible size, < 10KB per contract).

### Phase 3: Clause Intelligence & Playbooks
* **Vector Search**: Uses pgvector index on chunks within Neon DB.
* **Zero Cost Constraint**: Chunks are limited to top 15 candidate retrievals to keep query latency low on free compute.

### Phase 4: Collaboration & Workflows
* **WebSockets**: Supported natively over Render/Koyeb free tier.
* **Audit Logs**: Stored with automated monthly log rotation/pruning to stay comfortably within the 0.5 GB Postgres limit.

### Phase 5: Integrations & Notifications
* **Email**: Configured with free SMTP (Gmail App Password) or Resend API key.
* **Slack**: Outbound HTTPS webhooks are 100% free with 0 infrastructure dependencies.

### Phase 7 / Feature Plans Deployment Strategy:

| Feature Plan | Technical Requirement | $0 Free Tier Implementation |
|---|---|---|
| **Feature 1: Document Visualizer** | D3.js interactive graph | Client-side rendering via CDN (`d3.v7.min.js`); adjacency queries executed in PostgreSQL. 0 extra server cost. |
| **Feature 2: Collaborative Workspace** | Multi-user real-time chat & scoped RAG | WebSocket channels managed in-memory via `WebSocketManager`; messages stored in PostgreSQL. |
| **Feature 3: Contract Inbox & Triage** | Automated classification on upload | Ingestion triggers triage via FastAPI `BackgroundTasks`. Classification uses prompt caching & first 2000 tokens for minimal latency. |
| **Feature 4: Negotiation Tracker** | Multi-version diffing & timeline | `ClauseDiffer` computes word-level diffs in-memory; results stored in PostgreSQL. |
| **Feature 5: Cross-Contract Intelligence** | Heatmap & vendor scorecards | Aggregations cached in **Upstash Redis** (5-15 min TTL) to avoid hitting database compute limits. |

---

## 5. Ready-to-Deploy $0 Cloud Blueprint (Render + Neon + Upstash)

### Step 1: Create Free PostgreSQL with pgvector (Neon.tech)
1. Go to [Neon.tech](https://neon.tech/) and sign up (Free).
2. Create a project named `termnova`.
3. In the SQL Editor, run:
   ```sql
   CREATE EXTENSION IF NOT EXISTS vector;
   ```
4. Copy your Connection String (e.g., `postgresql://termnova_owner:password@ep-xyz.us-east-2.aws.neon.tech/termnova?sslmode=require`).

### Step 2: Create Free Serverless Redis (Upstash)
1. Go to [Upstash.com](https://upstash.com/) and sign up (Free).
2. Create a Redis database named `termnova-cache` (Primary region: US-East / Ohio / Oregon).
3. Copy the `rediss://default:password@xyz.upstash.io:6379` connection string.

### Step 3: Deploy FastAPI Application on Render (Free)
1. In [Render Dashboard](https://dashboard.render.com/), click **New +** $\rightarrow$ **Web Service**.
2. Connect your GitHub repository `termnova`.
3. Configure settings:
   - **Environment**: Docker
   - **Plan**: Free ($0/mo)
   - **Region**: Oregon (or nearest to your DB)
   - **Health Check Path**: `/health`
4. Add Environment Variables:
   ```env
   APP_ENV=production
   DATABASE_URL=postgresql+asyncpg://<NEON_USER>:<NEON_PASSWORD>@<NEON_HOST>/termnova?ssl=require
   DATABASE_URL_SYNC=postgresql://<NEON_USER>:<NEON_PASSWORD>@<NEON_HOST>/termnova?sslmode=require
   REDIS_URL=rediss://default:<UPSTASH_PASSWORD>@<UPSTASH_HOST>:6379
   LLM_PROVIDER=openai
   OPENAI_API_KEY=your-openai-api-key
   LLM_MODEL=gpt-4o-mini
   EMBEDDING_MODEL=text-embedding-3-small
   EMBEDDING_DIMENSION=1536
   ```
5. Click **Deploy Web Service**. Render provides a live URL (e.g., `https://termnova.onrender.com`).

---

## 6. Alternative Zero-Cost Deployment: Cloudflare Tunnel (Self-Hosted)

If you prefer to host from your own machine with **unlimited storage (1TB)** and **unlimited compute** with zero hosting bills:

```bash
# 1. Install cloudflared on Linux
curl -L --output cloudflared.deb https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
sudo dpkg -i cloudflared.deb

# 2. Start local Termnova stack with Docker
docker compose up -d

# 3. Create a quick, free public tunnel with Auto-HTTPS
cloudflared tunnel --url http://localhost:8000
```
This gives you an instant, secure public HTTPS URL (e.g. `https://xyz-random.trycloudflare.com`) routing directly to your local Termnova instance with enterprise DDoS protection and SSL.

---

## 7. Cost Guardrails & Limits Management

To ensure operations stay permanently within free boundaries:
1. **Sleep-Wake Resilience**: Render free services spin down after 15 minutes of inactivity. The health check (`/health`) auto-wakes the instance in ~20 seconds.
2. **Database Pruning**: A lightweight weekly maintenance query purges query logs older than 90 days if storage approaches 400 MB.
3. **Redis Key Expiry**: All cached intelligence and query logs in Upstash are set with explicit TTLs (300s to 900s) to prevent unbounded memory growth.
4. **Token Cost Optimization**: Contract triage and classification analyze the first ~2,000 tokens of contracts, keeping OpenAI API costs under $0.002 per uploaded document.
