"""Termnova Evaluation Framework: RAGAS Metrics, Benchmark Dataset, and Reporting."""

from dataclasses import dataclass, field


@dataclass
class EvalSample:
    """A benchmark Q&A evaluation test case."""

    id: str
    query: str
    ground_truth_answer: str
    ground_truth_contexts: list[str]
    source_document: str
    source_page: int
    difficulty: str
    category: str


@dataclass
class SampleEvalResult:
    """Detailed scores for a single evaluation case."""

    sample_id: str
    query: str
    predicted_answer: str
    ground_truth: str
    faithfulness: float
    answer_relevance: float
    context_precision: float
    context_recall: float
    citations_count: int
    latency_ms: int
    category: str
    difficulty: str
    passed: bool


@dataclass
class EvaluationReport:
    """Aggregated evaluation benchmark report across all test cases."""

    total_samples: int
    overall_faithfulness: float
    overall_relevance: float
    overall_precision: float
    overall_recall: float
    overall_pass_rate: float
    avg_latency_ms: float
    category_scores: dict[str, dict[str, float]]
    difficulty_scores: dict[str, dict[str, float]]
    sample_results: list[SampleEvalResult] = field(default_factory=list)


__all__ = [
    "EvalSample",
    "SampleEvalResult",
    "EvaluationReport",
]
