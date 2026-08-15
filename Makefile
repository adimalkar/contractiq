# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ContractIQ — Production RAG Engine Automation Makefile
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

.PHONY: setup dev docker-up docker-down docker-reset test test-all test-unit test-integration test-cov lint format typecheck ingest evaluate worker flower load-test clean

PYTHON ?= .venv/bin/python
PIP ?= .venv/bin/pip
UVICORN ?= .venv/bin/uvicorn
PYTEST ?= .venv/bin/pytest
RUFF ?= .venv/bin/ruff
MYPY ?= .venv/bin/mypy
CELERY ?= .venv/bin/celery
LOCUST ?= .venv/bin/locust

setup:
	python3 -m venv .venv
	$(PIP) install --upgrade pip setuptools wheel
	$(PIP) install -e ".[all]"

dev:
	$(PYTHON) -m uvicorn contractiq.api.main:app --reload --host 0.0.0.0 --port 8000

worker:
	$(CELERY) -A contractiq.pipeline.celery_app worker -l info -Q ingestion -c 2

flower:
	$(CELERY) -A contractiq.pipeline.celery_app flower --port=5555

docker-up:
	docker compose up -d

docker-down:
	docker compose down

docker-reset:
	docker compose down -v
	docker compose up -d

test:
	$(PYTEST) tests/ -m "not e2e" -v

test-unit:
	$(PYTEST) tests/unit/ -v

test-integration:
	$(PYTEST) tests/integration/ -v

test-all:
	$(PYTEST) tests/ -v

test-cov:
	$(PYTEST) tests/ --cov=src/contractiq --cov-report=term-missing --cov-report=html

load-test:
	$(LOCUST) -f tests/load/locustfile.py --host=http://localhost:8000 --headless -u 20 -r 5 -t 30s

lint:
	$(RUFF) check src/ tests/
	$(RUFF) format --check src/ tests/

format:
	$(RUFF) check --fix src/ tests/
	$(RUFF) format src/ tests/

typecheck:
	$(MYPY) src/

ingest:
	$(PYTHON) -m contractiq.pipeline.ingestion $(ARGS)

evaluate:
	$(PYTHON) -m contractiq.evaluation.runner

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".ruff_cache" -exec rm -rf {} +
	find . -type d -name ".mypy_cache" -exec rm -rf {} +
	rm -rf build/ dist/ htmlcov/ .coverage
