# ContractIQ Deployment & Operations Guide

This guide covers local environment setup, containerized Docker orchestration, and cloud deployment procedures.

---

## 1. Prerequisites

- **Python:** Version 3.11 or higher
- **PostgreSQL:** Version 14+ (or Docker image `pgvector/pgvector:pg16`)
- **Redis:** Version 6+ (or Docker image `redis:7-alpine`)
- **Memory:** Minimum 2 GB RAM (4 GB recommended for dense embedding models)

---

## 2. Local Bare-Metal Development

### Step 1: Clone and Set Up Virtual Environment
```bash
git clone https://github.com/adimalkar/contractiq.git
cd contractiq

python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip setuptools wheel
pip install -e ".[all]"
```

### Step 2: Configure Environment
```bash
cp .env.example .env
# Edit .env to set your OpenAI/AWS keys and database credentials
```

### Step 3: Initialize Database Schema
```bash
psql -d postgres -c "CREATE DATABASE contractiq;"
psql -d contractiq -f db/init/01_schema.sql
```

### Step 4: Run Development Server
```bash
make dev
# Application will start at http://localhost:8000
```

---

## 3. Containerized Deployment (Docker Compose)

The repository provides a production multi-container setup running PostgreSQL with native `pgvector`, Redis cache, and the FastAPI application.

### Start Infrastructure
```bash
# Start all containers in background
docker compose up -d

# Verify container health status
docker compose ps
```

### View Application Logs
```bash
docker compose logs -f api
```

### Ingest Contracts inside Container
```bash
docker compose exec api python -m contractiq.pipeline.ingestion /app/data/eval/sample_contracts/
```

### Stop Containers
```bash
docker compose down
```

---

## 4. Cloud Deployment Strategies

### Option A: AWS ECS Fargate & Amazon RDS (PostgreSQL)
1. **Database:** Provision Amazon RDS PostgreSQL 16 instance. Enable `pgvector` extension:
   ```sql
   CREATE EXTENSION vector;
   ```
2. **Caching:** Provision Amazon ElastiCache for Redis cluster.
3. **Container Registry:** Build and push Docker image to Amazon ECR:
   ```bash
   aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com
   docker build -t contractiq:latest .
   docker tag contractiq:latest <ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/contractiq:latest
   docker push <ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/contractiq:latest
   ```
4. **Task Definition:** Configure AWS Secrets Manager for `OPENAI_API_KEY` and database credentials. Attach `BedrockFullAccess` IAM role if using AWS Bedrock foundation models.

---

## 5. Environment Variables Reference

| Variable | Type | Default | Description |
|---|---|---|---|
| `DATABASE_URL` | string | `postgresql+asyncpg://...` | Async SQLAlchemy PostgreSQL connection string |
| `REDIS_URL` | string | `redis://localhost:6379/0` | Redis caching connection string |
| `LLM_PROVIDER` | string | `openai` | Model provider backend (`openai`, `bedrock`, `ollama`, `mock`) |
| `OPENAI_API_KEY` | string | - | OpenAI API key for generation & embeddings |
| `AWS_REGION` | string | `us-east-1` | AWS region when using Bedrock |
| `LLM_MODEL` | string | `gpt-4o-mini` | Main LLM model identifier |
| `EMBEDDING_MODEL` | string | `text-embedding-3-small` | Embedding model identifier |
| `EMBEDDING_DIMENSION` | int | `1536` | Dimensionality of embedding vector |
| `CHUNK_SIZE` | int | `512` | Token chunk target size |
| `CHUNK_OVERLAP` | int | `64` | Token chunk overlap |
| `TOP_K_RETRIEVAL` | int | `10` | Number of candidate chunks retrieved |
| `RELEVANCE_THRESHOLD`| float | `0.30` | Minimum score threshold for grader filter |
