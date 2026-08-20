"""Termnova Cross-Contract Intelligence and Portfolio Analytics module."""

from termnova.intelligence.aggregator import PortfolioAggregator
from termnova.intelligence.cache import IntelligenceCache
from termnova.intelligence.clause_analyzer import (
    CLAUSE_KEYS,
    CLAUSE_TAXONOMY,
    ClausePresenceAnalyzer,
)
from termnova.intelligence.schemas import (
    BenchmarkCategoryDelta,
    BenchmarkResult,
    ClauseHeatmapData,
    GapDetection,
    HeatmapCell,
    HeatmapColumnSummary,
    HeatmapRow,
    PortfolioSummary,
    TrendData,
    TrendDataPoint,
    VendorScorecard,
)

__all__ = [
    "CLAUSE_KEYS",
    "CLAUSE_TAXONOMY",
    "ClausePresenceAnalyzer",
    "PortfolioAggregator",
    "IntelligenceCache",
    "HeatmapCell",
    "HeatmapRow",
    "HeatmapColumnSummary",
    "ClauseHeatmapData",
    "VendorScorecard",
    "BenchmarkCategoryDelta",
    "BenchmarkResult",
    "TrendDataPoint",
    "TrendData",
    "GapDetection",
    "PortfolioSummary",
]
