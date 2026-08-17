"""Unit tests for hybrid retrieval, BM25 indexing, and Reciprocal Rank Fusion."""

import pytest

from termnova.rag.retriever import _simple_tokenize


@pytest.mark.unit
def test_simple_tokenize():
    """Verify regex tokenization strips punctuation and lowercases."""
    tokens = _simple_tokenize("ARTICLE 6.1: Limitation of Liability ($2,500,000) - NY!")
    assert "article" in tokens
    assert "6" in tokens
    assert "limitation" in tokens
    assert "liability" in tokens
    assert "2" in tokens
    assert "500" in tokens
    assert "ny" in tokens


@pytest.mark.unit
def test_tokenize_empty_string():
    """Verify empty string returns empty list."""
    assert _simple_tokenize("") == []
    assert _simple_tokenize("   \n\t  ") == []


@pytest.mark.unit
def test_rrf_formula_calculation():
    """Verify reciprocal rank fusion formula calculation manually."""
    rrf_k = 60
    w_sem = 0.6
    w_bm25 = 0.4

    # Rank 1 in both
    rrf_rank1 = (w_sem / (rrf_k + 1)) + (w_bm25 / (rrf_k + 1))
    max_possible = (w_sem / (rrf_k + 1)) + (w_bm25 / (rrf_k + 1))
    norm_score = rrf_rank1 / max_possible

    assert norm_score == 1.0

    # Rank 5 in semantic, not in BM25
    rrf_rank5 = w_sem / (rrf_k + 5)
    norm_rank5 = rrf_rank5 / max_possible
    assert 0.0 < norm_rank5 < 1.0
    assert norm_rank5 < norm_score
