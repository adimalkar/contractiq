"""Analytics, monitoring, and Responsible AI reporting endpoints."""

import structlog
from fastapi import APIRouter, Depends, Query

from contractiq.api.dependencies import get_repository
from contractiq.api.schemas import QualityAnalyticsResponse, UsageAnalyticsResponse
from contractiq.db.repository import ContractRepository

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/v1/analytics", tags=["Analytics & Quality Reporting"])


@router.get("/usage", response_model=UsageAnalyticsResponse)
async def get_usage_metrics(
    days: int = Query(default=30, ge=1, le=365, description="Lookback window in days"),
    repo: ContractRepository = Depends(get_repository),
) -> UsageAnalyticsResponse:
    """Retrieve operational usage, throughput, and latency metrics."""
    data = await repo.get_analytics_summary(days=days)
    return UsageAnalyticsResponse(
        total_queries=data["total_queries"],
        avg_latency_ms=data["avg_latency_ms"],
        avg_confidence=data["avg_confidence"],
        avg_faithfulness=data["avg_faithfulness"],
        top_queries=data["top_queries"],
        window_days=data["window_days"],
    )


@router.get("/quality", response_model=QualityAnalyticsResponse)
async def get_quality_metrics(
    days: int = Query(default=30, ge=1, le=365, description="Lookback window in days"),
    repo: ContractRepository = Depends(get_repository),
) -> QualityAnalyticsResponse:
    """Retrieve Responsible AI guardrails, hallucination rates, and quality score distributions."""
    data = await repo.get_quality_analytics(days=days)
    return QualityAnalyticsResponse(
        total_analyzed=data["total_analyzed"],
        hallucination_rate=data["hallucination_rate"],
        pii_redaction_rate=data["pii_redaction_rate"],
        score_distribution=data["score_distribution"],
    )
