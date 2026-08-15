"""Contract comparison and clause-level diff engine."""

import uuid
from dataclasses import dataclass, field


@dataclass
class ClauseAlignment:
    """A matched pair of clauses across two documents."""

    section_a: str | None
    section_b: str | None
    text_a: str
    text_b: str
    similarity_score: float
    diff_type: str  # "identical" | "modified" | "added" | "removed"
    diff_html: str


@dataclass
class ComparisonReport:
    """Full comparison analysis and metrics between two enterprise agreements."""

    comparison_id: uuid.UUID
    document_a_id: uuid.UUID
    document_b_id: uuid.UUID
    document_a_name: str
    document_b_name: str
    total_clauses_a: int
    total_clauses_b: int
    matched_clauses: int
    added_clauses: int
    removed_clauses: int
    modified_clauses: int
    identical_clauses: int
    overall_similarity: float
    alignments: list[ClauseAlignment] = field(default_factory=list)
    key_differences: list[str] = field(default_factory=list)


__all__ = [
    "ClauseAlignment",
    "ComparisonReport",
]
