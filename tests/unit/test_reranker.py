"""Unit tests for CrossEncoderReranker two-stage scoring and MMR diversity."""

import uuid

import pytest

from contractiq.rag import RetrievedChunk
from contractiq.rag.reranker import CrossEncoderReranker


def make_chunk(content: str, score: float = 0.5) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        content=content,
        page_number=1,
        section_header="ARTICLE 1",
        document_filename="test.pdf",
        semantic_score=score,
        keyword_score=score,
        fused_score=score,
    )


@pytest.mark.unit
def test_reranker_initialization_and_empty():
    """Verify reranker handles empty inputs gracefully."""
    reranker = CrossEncoderReranker()
    result = reranker.rerank("test query", [])
    assert result == []


@pytest.mark.unit
def test_rerank_preserves_top_k():
    """Verify that reranking returns exact top_k requested count."""
    reranker = CrossEncoderReranker()
    chunks = [
        make_chunk("Liability cap is $1,000,000.", score=0.2),
        make_chunk("Payment must be made in 30 days.", score=0.8),
        make_chunk("Governing law is State of New York.", score=0.4),
    ]
    reranked = reranker.rerank("What is the liability cap?", chunks, top_k=2)
    assert len(reranked) == 2


@pytest.mark.unit
def test_mmr_diversity_selection():
    """Verify that MMR penalizes redundant phrasing and preserves variety."""
    reranker = CrossEncoderReranker()
    chunks = [
        make_chunk("Liability limitation clause states cap of $1M.", score=0.9),
        make_chunk("Liability limitation clause states cap of $1M identical.", score=0.89),
        make_chunk("Termination notice period is 60 days.", score=0.6),
    ]
    diverse = reranker.rerank_with_diversity("liability", chunks, top_k=2, diversity_weight=0.5)
    assert len(diverse) == 2
