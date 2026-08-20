"""Pydantic v2 validation schemas for Cross-Contract Intelligence, Clause Heatmap, and Portfolio Analytics."""

import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field


class HeatmapCell(BaseModel):
    """Presence, risk score, and text excerpt of a clause category in a specific document."""

    category: str
    present: bool = False
    risk_level: Literal["low", "medium", "high", "critical"] | None = None
    excerpt: str | None = None
    confidence: float = 0.0
    chunk_id: uuid.UUID | None = None


class HeatmapRow(BaseModel):
    """Single contract row in the clause heatmap matrix."""

    document_id: uuid.UUID
    filename: str
    contract_type: str = "other"
    counterparty: str | None = None
    total_risk_score: float | None = None
    cells: dict[str, HeatmapCell] = Field(default_factory=dict)


class HeatmapColumnSummary(BaseModel):
    """Aggregate statistics for a specific clause category column."""

    category: str
    label: str
    present_count: int = 0
    total_count: int = 0
    coverage_pct: float = 0.0
    avg_risk: float | None = None
    high_risk_count: int = 0


class ClauseHeatmapData(BaseModel):
    """Full 2D clause heatmap matrix with document rows and category summaries."""

    rows: list[HeatmapRow] = []
    columns: list[str] = []
    column_summaries: list[HeatmapColumnSummary] = []
    total_documents: int = 0


class VendorScorecard(BaseModel):
    """Aggregate portfolio intelligence metrics for a specific counterparty/vendor."""

    entity_id: uuid.UUID | None = None
    entity_name: str
    entity_type: str = "counterparty"
    contract_count: int = 0
    total_value: float | None = None
    active_count: int = 0
    expired_count: int = 0
    avg_risk_score: float = 0.0
    risk_distribution: dict[str, int] = Field(default_factory=dict)
    clause_coverage: dict[str, float] = Field(default_factory=dict)
    playbook_deviation: float | None = None
    obligation_fulfillment_rate: float | None = None
    negotiation_trend: list[dict[str, Any]] = Field(default_factory=list)


class BenchmarkCategoryDelta(BaseModel):
    """Comparative delta for a single clause category in a benchmark score."""

    category: str
    this_contract_present: bool
    this_contract_risk: str | None
    portfolio_coverage_pct: float
    portfolio_avg_risk: str | None
    favorable_delta: bool = True


class BenchmarkResult(BaseModel):
    """Benchmark analysis ranking a specific contract against historical portfolio averages."""

    document_id: uuid.UUID
    document_filename: str
    contract_type: str
    overall_percentile: int  # 0 to 100 (higher = better/safer)
    risk_percentile: int
    clause_coverage_percentile: int
    comparison_summary: str
    category_breakdown: dict[str, BenchmarkCategoryDelta] = Field(default_factory=dict)


class TrendDataPoint(BaseModel):
    """Single period data point in portfolio trend analysis."""

    period: str  # e.g. "2025-Q1" or "2025-06"
    value: float
    contract_count: int


class TrendData(BaseModel):
    """Portfolio time-series trend analysis across a metric."""

    metric: Literal["risk", "value", "compliance"] = "risk"
    period: Literal["monthly", "quarterly"] = "monthly"
    data_points: list[TrendDataPoint] = []
    trend_direction: Literal["improving", "declining", "stable"] = "stable"
    change_pct: float = 0.0


class GapDetection(BaseModel):
    """Contract identified as missing mandatory/standard playbook clauses."""

    document_id: uuid.UUID
    filename: str
    contract_type: str
    missing_clauses: list[str] = []
    severity: Literal["low", "medium", "high", "critical"] = "medium"
    recommendation: str = ""


class PortfolioSummary(BaseModel):
    """Executive portfolio summary with KPI counts and top risks."""

    total_contracts: int = 0
    total_portfolio_value: float | None = None
    avg_risk_score: float = 0.0
    top_risks: list[str] = []
    expiring_in_30_days: int = 0
    compliance_score: float = 100.0
    trend_direction: Literal["improving", "declining", "stable"] = "stable"
