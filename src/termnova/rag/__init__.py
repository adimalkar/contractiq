"""Termnova RAG Engine: Hybrid Retrieval, Grading, Generation, and Guardrails."""

import uuid
from dataclasses import dataclass, field


@dataclass
class RetrievedChunk:
    """Candidate chunk returned by the hybrid retrieval layer."""

    chunk_id: uuid.UUID
    document_id: uuid.UUID
    content: str
    page_number: int | None
    section_header: str | None
    document_filename: str
    semantic_score: float
    keyword_score: float
    fused_score: float


@dataclass
class GradedChunk(RetrievedChunk):
    """Chunk enriched with relevance judgment and reasoning from the grader."""

    relevance_score: float = 0.0
    relevance_reasoning: str = ""
    is_relevant: bool = True


@dataclass
class Citation:
    """Explicit source attribution linking a claim to its underlying document chunk."""

    source_number: int
    chunk_id: uuid.UUID
    document_filename: str
    page_number: int | None
    section_header: str | None
    excerpt: str


@dataclass
class GeneratedAnswer:
    """Draft LLM response with parsed citations and generation metadata."""

    answer_text: str
    citations: list[Citation] = field(default_factory=list)
    model_used: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_ms: int = 0


@dataclass
class HallucinationFlag:
    """Audit finding when a generated claim is not entailed by retrieved context."""

    claim: str
    verdict: str  # "supported", "unsupported", "extrapolated"
    evidence: str


@dataclass
class GuardrailResult:
    """Post-generation quality, faithfulness, and privacy audit result."""

    faithfulness_score: float
    hallucination_flags: list[HallucinationFlag] = field(default_factory=list)
    pii_redacted: bool = False
    redacted_answer: str = ""
    confidence_score: float = 0.0
    passed: bool = True


@dataclass
class QueryResult:
    """Final unified response returned to client and API endpoints."""

    query_id: uuid.UUID
    query_text: str
    answer: str
    citations: list[Citation] = field(default_factory=list)
    confidence_score: float = 0.0
    faithfulness_score: float = 0.0
    hallucination_flags: list[HallucinationFlag] = field(default_factory=list)
    pii_redacted: bool = False
    retrieval_count: int = 0
    latency_ms: int = 0
    model_used: str = ""


__all__ = [
    "RetrievedChunk",
    "GradedChunk",
    "Citation",
    "GeneratedAnswer",
    "HallucinationFlag",
    "GuardrailResult",
    "QueryResult",
]
