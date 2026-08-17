"""Unit tests for RAG evaluation metrics (faithfulness, context precision, answer relevance)."""

import pytest

from termnova.evaluation.metrics import (
    compute_context_precision,
    compute_faithfulness,
)


@pytest.mark.unit
def test_compute_faithfulness_high_overlap():
    """Verify that an answer whose claims directly match context gets a high score."""
    contexts = [
        "The termination notice period is thirty (30) days written notice for convenience.",
        "Either party may terminate immediately for cause upon material breach.",
    ]
    answer = "The termination notice period requires thirty days written notice for convenience."

    score = compute_faithfulness(answer=answer, retrieved_contexts=contexts)
    assert score >= 0.8


@pytest.mark.unit
def test_compute_faithfulness_hallucination():
    """Verify that an answer introducing unsupported claims gets a low faithfulness score."""
    contexts = ["The supplier shall deliver all goods within 14 business days of PO receipt."]
    answer = "The supplier is subject to a $50,000 penalty if deliverables fail ISO 9001 compliance audit standards."

    score = compute_faithfulness(answer=answer, retrieved_contexts=contexts)
    assert score <= 0.4


@pytest.mark.unit
def test_compute_faithfulness_insufficient_information():
    """Verify that recognizing missing information is marked as 100% faithful."""
    contexts = ["Payment terms are net 30."]
    answer = "There is insufficient information in the provided context to answer the governing law question."

    score = compute_faithfulness(answer=answer, retrieved_contexts=contexts)
    assert score == 1.0


@pytest.mark.unit
def test_compute_context_precision():
    """Verify context precision correctly scores contexts containing ground truth answers."""
    contexts = [
        "The liability cap is equal to 12 months of fees paid under this agreement.",
        "Force majeure includes acts of god, war, and natural disasters.",
    ]
    ground_truth_contexts = ["12 months of fees paid"]

    score = compute_context_precision(
        ground_truth_contexts=ground_truth_contexts,
        retrieved_contexts=contexts,
    )
    assert score > 0.0
